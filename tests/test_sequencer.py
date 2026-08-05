from __future__ import annotations

from bouncebeat.midi.parser import inspect_midi
from bouncebeat.midi.sequencer import NoteSequencer, group_notes_into_chords
from bouncebeat.models.enums import MidiMappingMode
from bouncebeat.models.scene import MidiPlaybackSettings


def make_sequencer(path, mode: MidiMappingMode, seed: int = 42, chord_window_ms: int = 35):
    asset = inspect_midi(path)
    settings = MidiPlaybackSettings(mapping_mode=mode, chord_window_ms=chord_window_ms)
    return asset, NoteSequencer(asset, ["track_1", "track_2"], settings, seed=seed)


def test_chord_grouping(demo_midi_path):
    asset = inspect_midi(demo_midi_path)
    chords = group_notes_into_chords(asset.get_track("track_1").notes, 20)
    assert [[note.pitch for note in chord.notes] for chord in chords] == [[60, 64], [67]]


def test_sequential_note_progression(demo_midi_path):
    _, seq = make_sequencer(demo_midi_path, MidiMappingMode.SEQUENTIAL)
    first = seq.trigger(0.0, object_track_ids=["track_1"])
    second = seq.trigger(0.1, object_track_ids=["track_1"])
    assert [event.pitch for event in first] == [60, 64]
    assert [event.pitch for event in second] == [67]


def test_layered_advances_each_selected_track(demo_midi_path):
    _, seq = make_sequencer(demo_midi_path, MidiMappingMode.LAYERED)
    events = seq.trigger(0.0)
    assert [event.track_id for event in events] == ["track_1", "track_1", "track_2"]
    assert {event.pitch for event in events} == {36, 60, 64}


def test_round_robin_track_selection(demo_midi_path):
    _, seq = make_sequencer(demo_midi_path, MidiMappingMode.ROUND_ROBIN)
    tracks = [seq.trigger(index * 0.1)[0].track_id for index in range(4)]
    assert tracks == ["track_1", "track_2", "track_1", "track_2"]


def test_random_track_is_reproducible(demo_midi_path):
    _, first = make_sequencer(demo_midi_path, MidiMappingMode.RANDOM_TRACK, seed=9)
    _, second = make_sequencer(demo_midi_path, MidiMappingMode.RANDOM_TRACK, seed=9)
    first_tracks = [first.trigger(index * 0.1)[0].track_id for index in range(8)]
    second_tracks = [second.trigger(index * 0.1)[0].track_id for index in range(8)]
    assert first_tracks == second_tracks
    assert len(set(first_tracks)) == 2


def test_mute_and_solo_are_applied(demo_midi_path):
    asset, seq = make_sequencer(demo_midi_path, MidiMappingMode.LAYERED)
    asset.get_track("track_2").muted = True
    assert {event.track_id for event in seq.trigger(0.0)} == {"track_1"}
    seq.reset()
    asset.get_track("track_2").muted = False
    asset.get_track("track_2").solo = True
    assert {event.track_id for event in seq.trigger(0.0)} == {"track_2"}


def test_timeline_synchronized_includes_notes_at_zero(demo_midi_path):
    _, seq = make_sequencer(demo_midi_path, MidiMappingMode.TIMELINE_SYNCHRONIZED)
    events = seq.timeline_events_due(0.0, 1 / 60)
    assert {event.pitch for event in events} == {36, 60, 64}


def test_polyphony_limit_applies_to_layered_chords(demo_midi_path):
    asset = inspect_midi(demo_midi_path)
    settings = MidiPlaybackSettings(mapping_mode=MidiMappingMode.LAYERED, polyphony_limit=2)
    seq = NoteSequencer(asset, ["track_1", "track_2"], settings, seed=1)
    assert len(seq.trigger(0.0)) == 2


def test_quantization_snaps_timeline_notes(demo_midi_path):
    asset = inspect_midi(demo_midi_path)
    settings = MidiPlaybackSettings(mapping_mode=MidiMappingMode.TIMELINE_SYNCHRONIZED, quantization="1/4")
    seq = NoteSequencer(asset, ["track_1"], settings, seed=1)
    starts = [note.start for note in seq._timeline_notes]
    assert all(abs((start / 0.5) - round(start / 0.5)) < 1e-9 for start in starts)
