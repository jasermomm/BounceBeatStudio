from __future__ import annotations

from pathlib import Path

import mido
import pytest


def create_demo_midi(path: Path) -> Path:
    midi = mido.MidiFile(type=1, ticks_per_beat=480)

    conductor = mido.MidiTrack()
    midi.tracks.append(conductor)
    conductor.append(mido.MetaMessage("track_name", name="Conductor", time=0))
    conductor.append(mido.MetaMessage("set_tempo", tempo=500_000, time=0))
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))

    piano = mido.MidiTrack()
    midi.tracks.append(piano)
    piano.append(mido.MetaMessage("track_name", name="Piano", time=0))
    piano.append(mido.Message("program_change", channel=0, program=0, time=0))

    piano.append(mido.Message("note_on", channel=0, note=60, velocity=96, time=0))
    piano.append(mido.Message("note_on", channel=0, note=64, velocity=88, time=0))
    piano.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=240))
    piano.append(mido.Message("note_off", channel=0, note=64, velocity=0, time=0))
    piano.append(mido.Message("note_on", channel=0, note=67, velocity=100, time=240))
    piano.append(mido.Message("note_off", channel=0, note=67, velocity=0, time=480))

    bass = mido.MidiTrack()
    midi.tracks.append(bass)
    bass.append(mido.MetaMessage("track_name", name="Bass", time=0))
    bass.append(mido.Message("program_change", channel=1, program=33, time=0))
    bass.append(mido.Message("note_on", channel=1, note=36, velocity=110, time=0))
    bass.append(mido.Message("note_off", channel=1, note=36, velocity=0, time=480))
    bass.append(mido.Message("note_on", channel=1, note=43, velocity=104, time=0))
    bass.append(mido.Message("note_off", channel=1, note=43, velocity=0, time=480))

    metadata = mido.MidiTrack()
    midi.tracks.append(metadata)
    metadata.append(mido.MetaMessage("track_name", name="Markers", time=0))
    metadata.append(mido.MetaMessage("marker", text="Verse", time=480))

    midi.save(path)
    return path


@pytest.fixture()
def demo_midi_path(tmp_path: Path) -> Path:
    return create_demo_midi(tmp_path / "piano_bass.mid")
