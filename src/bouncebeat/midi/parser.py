from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import mido

from bouncebeat.models.midi import MidiAsset, MidiNote, MidiTrackInfo

GM_INSTRUMENTS = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar harmonics",
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass", "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2", "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet", "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter", "Applause", "Gunshot",
]


class MidiParseError(ValueError):
    pass


def instrument_name(program: int, is_drum: bool = False) -> str:
    if is_drum:
        return "General MIDI Drums"
    if 0 <= program < len(GM_INSTRUMENTS):
        return GM_INSTRUMENTS[program]
    return f"Program {program}"


def _tempo_events(mid: mido.MidiFile) -> list[tuple[int, int]]:
    events: list[tuple[int, int, int]] = [(0, 500_000, -1)]
    for track_index, track in enumerate(mid.tracks):
        tick = 0
        for message in track:
            tick += message.time
            if message.type == "set_tempo":
                events.append((tick, int(message.tempo), track_index))
    events.sort(key=lambda item: (item[0], item[2]))
    collapsed: list[tuple[int, int]] = []
    for tick, tempo, _ in events:
        if collapsed and collapsed[-1][0] == tick:
            collapsed[-1] = (tick, tempo)
        else:
            collapsed.append((tick, tempo))
    return collapsed


def _tick_converter(ticks_per_beat: int, tempo_events: list[tuple[int, int]]):
    segments: list[tuple[int, float, int]] = []
    current_tick = 0
    current_seconds = 0.0
    current_tempo = 500_000
    for tick, tempo in tempo_events:
        if tick > current_tick:
            current_seconds += mido.tick2second(tick - current_tick, ticks_per_beat, current_tempo)
            current_tick = tick
        current_tempo = tempo
        segments.append((current_tick, current_seconds, current_tempo))

    def convert(tick: int) -> float:
        chosen = segments[0]
        for segment in segments:
            if segment[0] > tick:
                break
            chosen = segment
        base_tick, base_seconds, tempo = chosen
        return base_seconds + mido.tick2second(tick - base_tick, ticks_per_beat, tempo)

    return convert


def inspect_midi(path: str | Path) -> MidiAsset:
    midi_path = Path(path)
    if midi_path.suffix.lower() not in {".mid", ".midi"}:
        raise MidiParseError("Choose a .mid or .midi file.")
    if not midi_path.is_file():
        raise MidiParseError(f"MIDI file does not exist: {midi_path}")
    try:
        mid = mido.MidiFile(midi_path, clip=True)
    except (OSError, EOFError, ValueError) as exc:
        raise MidiParseError(f"Could not read MIDI file: {exc}") from exc

    tempo_events = _tempo_events(mid)
    to_seconds = _tick_converter(mid.ticks_per_beat, tempo_events)
    tracks: list[MidiTrackInfo] = []
    overall_duration = 0.0

    for track_index, track in enumerate(mid.tracks):
        absolute_tick = 0
        track_name = ""
        programs: dict[int, int] = defaultdict(int)
        note_starts: dict[tuple[int, int], list[tuple[int, int, int]]] = defaultdict(list)
        notes: list[MidiNote] = []
        seen_non_meta = False
        channel_counts: dict[int, int] = defaultdict(int)
        track_end_tick = 0

        for message in track:
            absolute_tick += int(message.time)
            track_end_tick = max(track_end_tick, absolute_tick)
            if message.type == "track_name" and not track_name:
                track_name = str(message.name).strip()
            if not message.is_meta:
                seen_non_meta = True
            if message.type == "program_change":
                programs[int(message.channel)] = int(message.program)
            elif message.type == "note_on" and message.velocity > 0:
                channel = int(message.channel)
                pitch = int(message.note)
                note_starts[(channel, pitch)].append(
                    (absolute_tick, int(message.velocity), programs[channel])
                )
                channel_counts[channel] += 1
            elif message.type in {"note_off", "note_on"} and (
                message.type == "note_off" or message.velocity == 0
            ):
                key = (int(message.channel), int(message.note))
                if note_starts[key]:
                    start_tick, velocity, program = note_starts[key].pop(0)
                    start = to_seconds(start_tick)
                    end = max(start + 0.001, to_seconds(absolute_tick))
                    notes.append(
                        MidiNote(
                            track_id=f"track_{track_index}",
                            track_index=track_index,
                            channel=key[0],
                            program=program,
                            pitch=key[1],
                            velocity=velocity,
                            start=start,
                            end=end,
                        )
                    )

        final_seconds = to_seconds(track_end_tick)
        for (channel, pitch), starts in note_starts.items():
            for start_tick, velocity, program in starts:
                start = to_seconds(start_tick)
                notes.append(
                    MidiNote(
                        track_id=f"track_{track_index}",
                        track_index=track_index,
                        channel=channel,
                        program=program,
                        pitch=pitch,
                        velocity=velocity,
                        start=start,
                        end=max(start + 0.1, final_seconds),
                    )
                )
        notes.sort(key=lambda note: (note.start, note.pitch, note.channel))
        note_channels = [note.channel for note in notes]
        dominant_channel = max(channel_counts, key=channel_counts.get) if channel_counts else 0
        is_drum = bool(note_channels) and all(channel == 9 for channel in note_channels)
        program = 0 if is_drum else programs[dominant_channel]
        duration = max((note.end for note in notes), default=final_seconds)
        overall_duration = max(overall_duration, duration)
        display_name = track_name or ("Drums" if is_drum else instrument_name(program))
        pitches = [note.pitch for note in notes]
        tracks.append(
            MidiTrackInfo(
                id=f"track_{track_index}",
                index=track_index,
                name=display_name,
                channel=dominant_channel,
                program=program,
                instrument_name=instrument_name(program, is_drum),
                note_count=len(notes),
                lowest_note=min(pitches) if pitches else None,
                highest_note=max(pitches) if pitches else None,
                duration=duration,
                is_drum=is_drum,
                is_empty=not seen_non_meta and not notes,
                is_metadata_only=not notes and any(message.is_meta for message in track),
                notes=notes,
            )
        )

    if not tracks:
        raise MidiParseError("The MIDI file contains no tracks.")
    return MidiAsset(
        path=str(midi_path.resolve()),
        ticks_per_beat=mid.ticks_per_beat,
        duration=overall_duration,
        tracks=tracks,
    )
