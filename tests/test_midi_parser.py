from __future__ import annotations

from bouncebeat.midi.parser import inspect_midi


def test_midi_track_extraction(demo_midi_path):
    asset = inspect_midi(demo_midi_path)
    assert asset.ticks_per_beat == 480
    assert len(asset.tracks) == 4
    assert len(asset.playable_tracks()) == 2

    piano = asset.get_track("track_1")
    bass = asset.get_track("track_2")
    markers = asset.get_track("track_3")
    assert piano is not None and piano.name == "Piano"
    assert piano.instrument_name == "Acoustic Grand Piano"
    assert piano.note_count == 3
    assert (piano.lowest_note, piano.highest_note) == (60, 67)
    assert bass is not None and bass.name == "Bass"
    assert "Bass" in bass.instrument_name
    assert bass.channel == 1
    assert bass.note_count == 2
    assert markers is not None and markers.is_metadata_only and markers.note_count == 0


def test_multiple_track_selection_data_is_preserved(demo_midi_path):
    asset = inspect_midi(demo_midi_path)
    selected = [track.id for track in asset.playable_tracks()]
    assert selected == ["track_1", "track_2"]
    assert asset.get_track(selected[0]).program == 0
    assert asset.get_track(selected[1]).program == 33
