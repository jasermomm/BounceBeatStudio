from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import mido
import numpy as np
import soundfile as sf

from bouncebeat.models.events import NoteEvent


def _wave(phase: np.ndarray, waveform: str) -> np.ndarray:
    if waveform == "square":
        return np.where(np.sin(phase) >= 0, 1.0, -1.0)
    if waveform == "triangle":
        return 2.0 / math.pi * np.arcsin(np.sin(phase))
    if waveform == "sawtooth":
        return 2.0 * ((phase / (2 * math.pi)) % 1.0) - 1.0
    return np.sin(phase)


def render_fallback_audio(
    note_events: list[NoteEvent],
    duration: float,
    sample_rate: int = 48000,
    waveform: str = "sine",
    master_volume: float = 0.8,
) -> np.ndarray:
    sample_count = max(1, round(duration * sample_rate))
    audio = np.zeros((sample_count, 2), dtype=np.float32)
    for event in sorted(note_events, key=lambda item: (item.time, item.pitch, item.track_id)):
        start = max(0, round(event.time * sample_rate))
        end = min(sample_count, start + max(1, round(event.duration * sample_rate)))
        if end <= start:
            continue
        count = end - start
        frequency = 440.0 * (2.0 ** ((event.pitch - 69) / 12.0))
        t = np.arange(count, dtype=np.float64) / sample_rate
        signal = _wave(2 * math.pi * frequency * t, waveform).astype(np.float32)
        attack_samples = max(1, round(sample_rate * 0.008))
        release_samples = max(1, min(count, round(sample_rate * 0.06)))
        envelope = np.ones(count, dtype=np.float32)
        envelope[: min(count, attack_samples)] = np.linspace(0, 1, min(count, attack_samples), dtype=np.float32)
        envelope[-release_samples:] *= np.linspace(1, 0, release_samples, dtype=np.float32)
        gain = (event.velocity / 127.0) * event.volume * master_volume * 0.22
        signal *= envelope * gain
        pan = max(-1.0, min(1.0, event.pan))
        audio[start:end, 0] += signal * math.sqrt((1 - pan) * 0.5)
        audio[start:end, 1] += signal * math.sqrt((1 + pan) * 0.5)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0.98:
        audio *= 0.98 / peak
    return audio


def _write_event_midi(note_events: list[NoteEvent], destination: Path) -> None:
    """Write render events without prematurely ending overlapping equal pitches.

    Standard MIDI note-off messages do not carry a note instance identifier. When
    two events overlap on the same channel and pitch, emitting the first note-off
    normally silences both voices in many synths. We therefore keep a small
    reference count and emit note-off only when the final overlapping event ends.
    """
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    tempo = 500_000
    by_track: dict[str, list[NoteEvent]] = {}
    for event in note_events:
        by_track.setdefault(event.track_id or "events", []).append(event)
    for track_id, events in sorted(by_track.items()):
        track = mido.MidiTrack()
        midi.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=track_id, time=0))
        actions: list[tuple[int, int, str, int, int, int, int]] = []
        programs: set[tuple[int, int]] = set()
        for event in events:
            channel = int(event.channel) % 16
            program = int(event.program) % 128
            if (channel, program) not in programs:
                programs.add((channel, program))
                actions.append((0, -1, "program", channel, 0, 0, program))
            start_tick = round(mido.second2tick(event.time, midi.ticks_per_beat, tempo))
            end_tick = round(mido.second2tick(event.time + event.duration, midi.ticks_per_beat, tempo))
            actions.append((start_tick, 1, "on", channel, int(event.pitch), int(event.velocity), program))
            actions.append((max(start_tick + 1, end_tick), 0, "off", channel, int(event.pitch), 0, program))

        actions.sort(key=lambda item: (item[0], item[1], item[3], item[4]))
        active: dict[tuple[int, int], int] = {}
        output: list[tuple[int, mido.Message]] = []
        for tick, _priority, kind, channel, pitch, velocity, program in actions:
            key = (channel, pitch)
            if kind == "program":
                output.append((tick, mido.Message("program_change", channel=channel, program=program, time=0)))
            elif kind == "on":
                active[key] = active.get(key, 0) + 1
                output.append((tick, mido.Message("note_on", channel=channel, note=pitch, velocity=velocity, time=0)))
            else:
                remaining = active.get(key, 0) - 1
                if remaining > 0:
                    active[key] = remaining
                else:
                    active.pop(key, None)
                    output.append((tick, mido.Message("note_off", channel=channel, note=pitch, velocity=0, time=0)))

        output.sort(key=lambda item: item[0])
        last_tick = 0
        for tick, message in output:
            message.time = tick - last_tick
            last_tick = tick
            track.append(message)
    midi.save(destination)


def render_with_fluidsynth_cli(
    note_events: list[NoteEvent],
    duration: float,
    output_path: Path,
    soundfont_path: str,
    sample_rate: int,
    master_volume: float = 0.8,
) -> bool:
    executable = shutil.which("fluidsynth")
    if not executable or not Path(soundfont_path).is_file():
        return False
    with tempfile.TemporaryDirectory(prefix="bouncebeat-midi-") as temporary:
        midi_path = Path(temporary) / "events.mid"
        _write_event_midi(note_events, midi_path)
        command = [
            executable, "-ni", "-F", str(output_path), "-r", str(sample_rate),
            "-g", f"{max(0.0, min(10.0, master_volume)):.4f}",
            "-T", "wav", soundfont_path, str(midi_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not output_path.is_file():
            return False
        _conform_wav_duration(output_path, duration, sample_rate)
        return True


def _conform_wav_duration(path: Path, duration: float, sample_rate: int) -> None:
    """Force external synth output to exact stereo duration for A/V sync."""
    target_count = max(1, round(max(0.0, duration) * sample_rate))
    data, source_rate = sf.read(path, dtype="float32", always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    if source_rate != sample_rate and len(data) > 1:
        source_times = np.arange(len(data), dtype=np.float64) / source_rate
        target_times = np.arange(target_count, dtype=np.float64) / sample_rate
        channels = [
            np.interp(target_times, source_times, data[:, index], left=0.0, right=0.0)
            for index in range(data.shape[1])
        ]
        data = np.column_stack(channels).astype(np.float32)
    elif len(data) < target_count:
        data = np.pad(data, ((0, target_count - len(data)), (0, 0)))
    else:
        data = data[:target_count]
    sf.write(path, data, sample_rate, subtype="PCM_16")


def render_note_events_to_wav(
    note_events: list[NoteEvent],
    duration: float,
    output_path: str | Path,
    sample_rate: int = 48000,
    waveform: str = "sine",
    master_volume: float = 0.8,
    soundfont_path: str = "",
) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if soundfont_path and render_with_fluidsynth_cli(
        note_events, duration, destination, soundfont_path, sample_rate, master_volume
    ):
        return destination
    audio = render_fallback_audio(note_events, duration, sample_rate, waveform, master_volume)
    sf.write(destination, audio, sample_rate, subtype="PCM_16")
    return destination
