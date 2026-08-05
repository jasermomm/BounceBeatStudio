from __future__ import annotations

from pathlib import Path

import mido


def create(path: Path) -> None:
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    conductor = mido.MidiTrack(); midi.tracks.append(conductor)
    conductor.append(mido.MetaMessage("track_name", name="Conductor", time=0))
    conductor.append(mido.MetaMessage("set_tempo", tempo=500_000, time=0))

    piano = mido.MidiTrack(); midi.tracks.append(piano)
    piano.append(mido.MetaMessage("track_name", name="Piano", time=0))
    piano.append(mido.Message("program_change", channel=0, program=0, time=0))
    for root in (60, 65, 67, 60):
        for index, pitch in enumerate((root, root + 4, root + 7)):
            piano.append(mido.Message("note_on", channel=0, note=pitch, velocity=92, time=0 if index else 0))
        piano.append(mido.Message("note_off", channel=0, note=root, velocity=0, time=360))
        piano.append(mido.Message("note_off", channel=0, note=root + 4, velocity=0, time=0))
        piano.append(mido.Message("note_off", channel=0, note=root + 7, velocity=0, time=0))
        piano.append(mido.MetaMessage("marker", text="next", time=120))

    bass = mido.MidiTrack(); midi.tracks.append(bass)
    bass.append(mido.MetaMessage("track_name", name="Bass", time=0))
    bass.append(mido.Message("program_change", channel=1, program=33, time=0))
    for pitch in (36, 41, 43, 36):
        bass.append(mido.Message("note_on", channel=1, note=pitch, velocity=110, time=0))
        bass.append(mido.Message("note_off", channel=1, note=pitch, velocity=0, time=480))

    path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(path)


if __name__ == "__main__":
    create(Path(__file__).resolve().parents[1] / "src" / "bouncebeat" / "assets" / "demo" / "piano_bass_demo.mid")
