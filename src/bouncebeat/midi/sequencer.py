from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Iterable

from bouncebeat.models.enums import MidiMappingMode
from bouncebeat.models.events import NoteEvent
from bouncebeat.models.midi import MidiAsset, MidiNote, MidiTrackInfo
from bouncebeat.models.scene import MidiPlaybackSettings


@dataclass(slots=True)
class Chord:
    notes: list[MidiNote]

    @property
    def start(self) -> float:
        return min((note.start for note in self.notes), default=0.0)


def group_notes_into_chords(notes: Iterable[MidiNote], window_ms: int) -> list[Chord]:
    sorted_notes = sorted(notes, key=lambda note: (note.start, note.pitch, note.channel))
    if not sorted_notes:
        return []
    window = max(0.0, window_ms / 1000.0)
    groups: list[Chord] = []
    current: list[MidiNote] = [sorted_notes[0]]
    anchor = sorted_notes[0].start
    for note in sorted_notes[1:]:
        if note.start - anchor <= window:
            current.append(note)
        else:
            groups.append(Chord(current))
            current = [note]
            anchor = note.start
    groups.append(Chord(current))
    return groups


_SCALE_PITCH_CLASSES = {
    "chromatic": set(range(12)),
    "major": {0, 2, 4, 5, 7, 9, 11},
    "minor": {0, 2, 3, 5, 7, 8, 10},
    "pentatonic": {0, 2, 4, 7, 9},
}


class NoteSequencer:
    def __init__(
        self,
        midi_asset: MidiAsset,
        selected_track_ids: list[str],
        settings: MidiPlaybackSettings,
        seed: int = 1337,
    ) -> None:
        self.asset = midi_asset
        self.settings = settings
        self.seed = seed
        self.rng = random.Random(seed)
        self.selected_track_ids = [
            track_id for track_id in selected_track_ids if midi_asset.get_track(track_id)
        ]
        self.track_chords: dict[str, list[Chord]] = {}
        self.indices: dict[str, int] = defaultdict(int)
        self.round_robin_index = 0
        self.timeline_cursor = 0.0
        self._timeline_notes: list[MidiNote] = []
        self._prepare()

    def _prepare(self) -> None:
        self.track_chords.clear()
        self._timeline_notes.clear()
        for track_id in self.selected_track_ids:
            track = self.asset.get_track(track_id)
            if track is None:
                continue
            notes = list(track.notes)
            if self.settings.quantization != "off":
                try:
                    denominator = int(self.settings.quantization.split("/", 1)[1])
                    grid = 0.5 * 4 / max(1, denominator)
                    quantized = []
                    for note in notes:
                        duration = note.duration
                        start = round(note.start / grid) * grid
                        quantized.append(replace(note, start=start, end=max(start + 0.001, start + duration)))
                    notes = quantized
                except (ValueError, IndexError):
                    pass
            if self.settings.scale_filter != "chromatic":
                allowed = _SCALE_PITCH_CLASSES.get(self.settings.scale_filter, set(range(12)))
                notes = [note for note in notes if note.pitch % 12 in allowed]
            if self.settings.reverse_order:
                notes.reverse()
            if self.settings.shuffle_order:
                self.rng.shuffle(notes)
            self.track_chords[track_id] = group_notes_into_chords(
                notes, self.settings.chord_window_ms
            )
            self._timeline_notes.extend(notes)
        self._timeline_notes.sort(key=lambda note: (note.start, note.track_index, note.pitch))

    def reset(self) -> None:
        self.rng = random.Random(self.seed)
        self.indices.clear()
        self.round_robin_index = 0
        self.timeline_cursor = 0.0
        self._prepare()

    def _track_enabled(self, track: MidiTrackInfo) -> bool:
        solo_tracks = [item for item in self.asset.tracks if item.solo]
        if solo_tracks and not track.solo:
            return False
        return not track.muted and track.volume > 0

    def track_enabled(self, track_id: str) -> bool:
        track = self.asset.get_track(track_id)
        return bool(track and self._track_enabled(track))

    @property
    def timeline_notes(self) -> tuple[MidiNote, ...]:
        return tuple(
            note for note in self._timeline_notes
            if self.track_enabled(note.track_id)
        )


    def timeline_occurrences_between(
        self, previous_time: float, current_time: float, *, lead_in_seconds: float = 0.0
    ) -> list[tuple[float, MidiNote]]:
        if not self._timeline_notes or current_time < previous_time:
            return []
        tempo = max(0.01, self.settings.tempo_multiplier)
        lead_in = max(0.0, float(lead_in_seconds))
        shifted_start = previous_time - lead_in
        shifted_end = current_time - lead_in
        if shifted_end < -1e-12:
            return []
        midi_start = max(0.0, shifted_start * tempo)
        midi_end = max(0.0, shifted_end * tempo)
        include_zero = shifted_start <= 1e-12
        duration = max(self.asset.duration, 0.001)
        occurrences: list[tuple[float, MidiNote]] = []
        notes = self.timeline_notes
        if self.settings.loop:
            first_cycle = max(0, int(midi_start // duration))
            last_cycle = max(first_cycle, int(midi_end // duration))
            for cycle in range(first_cycle, last_cycle + 1):
                offset = cycle * duration
                for note in notes:
                    occurrence = offset + note.start
                    after_start = occurrence > midi_start + 1e-12 or (include_zero and occurrence >= -1e-12)
                    if after_start and occurrence <= midi_end + 1e-12:
                        occurrences.append((lead_in + occurrence / tempo, note))
        else:
            for note in notes:
                occurrence = note.start
                after_start = occurrence > midi_start + 1e-12 or (include_zero and occurrence >= -1e-12)
                if after_start and occurrence <= midi_end + 1e-12:
                    occurrences.append((lead_in + occurrence / tempo, note))
        occurrences.sort(key=lambda item: (item[0], item[1].track_index, item[1].pitch))
        return occurrences

    def _next_chord(self, track_id: str) -> Chord | None:
        chords = self.track_chords.get(track_id, [])
        if not chords:
            return None
        index = self.indices[track_id]
        if index >= len(chords):
            if not self.settings.loop:
                return None
            index = 0
        chord = chords[index]
        self.indices[track_id] = index + 1
        return chord

    def _event(self, note: MidiNote, time: float, strength: float, source_id: str) -> NoteEvent:
        pitch = note.pitch + self.settings.transpose + self.settings.octave_shift * 12
        if self.settings.strength_controls_pitch:
            pitch += round(max(-12.0, min(12.0, (strength - 500.0) / 150.0)))
        pitch = max(0, min(127, pitch))
        velocity = round(note.velocity * self.settings.velocity_multiplier)
        if self.settings.strength_controls_velocity:
            velocity = round(velocity * max(0.25, min(1.5, strength / 700.0)))
        velocity = max(self.settings.minimum_velocity, min(self.settings.maximum_velocity, velocity))
        duration = self.settings.note_duration_ms / 1000.0
        if self.settings.sustain:
            duration = max(duration, note.duration / max(0.01, self.settings.tempo_multiplier))
        if self.settings.strength_controls_duration:
            duration *= max(0.35, min(2.0, strength / 600.0))
        track = self.asset.get_track(note.track_id)
        track_volume = track.volume if track else 1.0
        if self.settings.strength_controls_volume:
            track_volume *= max(0.2, min(1.5, strength / 650.0))
        channel = self.settings.channel_override if self.settings.channel_override is not None else note.channel
        program = self.settings.instrument_override if self.settings.instrument_override is not None else note.program
        return NoteEvent(
            time=time,
            pitch=pitch,
            velocity=velocity,
            duration=max(0.02, duration),
            track_id=note.track_id,
            channel=channel,
            program=program,
            pan=track.pan if track else 0.0,
            volume=max(0.0, min(2.0, track_volume)),
            source_object_id=source_id,
        )

    def _events_from_chord(self, chord: Chord | None, time: float, strength: float, source_id: str) -> list[NoteEvent]:
        if chord is None:
            return []
        events: list[NoteEvent] = []
        for note in chord.notes:
            track = self.asset.get_track(note.track_id)
            if track and self._track_enabled(track):
                events.append(self._event(note, time, strength, source_id))
        return events

    def _limit(self, events: list[NoteEvent]) -> list[NoteEvent]:
        return events[: max(1, self.settings.polyphony_limit)]

    def trigger(
        self,
        time: float,
        strength: float = 500.0,
        source_object_id: str = "",
        object_track_ids: list[str] | None = None,
        surface_track_ids: list[str] | None = None,
    ) -> list[NoteEvent]:
        mode = self.settings.mapping_mode
        selected = self.selected_track_ids
        if not selected:
            return []

        if mode == MidiMappingMode.LAYERED:
            events: list[NoteEvent] = []
            for track_id in selected:
                events.extend(self._events_from_chord(self._next_chord(track_id), time, strength, source_object_id))
            return self._limit(events)

        if mode == MidiMappingMode.ROUND_ROBIN:
            track_id = selected[self.round_robin_index % len(selected)]
            self.round_robin_index += 1
            return self._limit(self._events_from_chord(self._next_chord(track_id), time, strength, source_object_id))

        if mode == MidiMappingMode.RANDOM_TRACK:
            track_id = self.rng.choice(selected)
            return self._limit(self._events_from_chord(self._next_chord(track_id), time, strength, source_object_id))

        if mode == MidiMappingMode.PER_BALL:
            candidates = [track_id for track_id in (object_track_ids or []) if track_id in selected]
            track_id = candidates[0] if candidates else selected[0]
            return self._limit(self._events_from_chord(self._next_chord(track_id), time, strength, source_object_id))

        if mode == MidiMappingMode.PER_SURFACE:
            candidates = [track_id for track_id in (surface_track_ids or []) if track_id in selected]
            track_id = candidates[0] if candidates else selected[0]
            return self._limit(self._events_from_chord(self._next_chord(track_id), time, strength, source_object_id))

        if mode == MidiMappingMode.COLLISION_CONTROLLED_TIMELINE:
            if not self._timeline_notes:
                return []
            next_start = next(
                (note.start for note in self._timeline_notes if note.start >= self.timeline_cursor - 1e-9),
                None,
            )
            if next_start is None:
                if not self.settings.loop:
                    return []
                self.timeline_cursor = 0.0
                next_start = self._timeline_notes[0].start
            window = self.settings.chord_window_ms / 1000.0
            due = [note for note in self._timeline_notes if next_start <= note.start <= next_start + window]
            self.timeline_cursor = next_start + window + 1e-6
            return self._limit([self._event(note, time, strength, source_object_id) for note in due])


        candidates = [track_id for track_id in (object_track_ids or []) if track_id in selected]
        track_id = candidates[0] if candidates else selected[0]
        return self._limit(self._events_from_chord(self._next_chord(track_id), time, strength, source_object_id))

    def timeline_events_due(self, previous_time: float, current_time: float) -> list[NoteEvent]:
        if self.settings.mapping_mode != MidiMappingMode.TIMELINE_SYNCHRONIZED:
            return []
        occurrences = self.timeline_occurrences_between(previous_time, current_time)
        events = [
            self._event(note, occurrence, note.velocity / 127.0 * 900.0, "timeline")
            for occurrence, note in occurrences
        ]
        return self._limit(events)
