from __future__ import annotations

import math
from pathlib import Path

import mido
import numpy as np
import soundfile as sf

from bouncebeat.audio.offline import _conform_wav_duration, _write_event_midi, render_fallback_audio
from bouncebeat.audio.synth import PolySynth
from bouncebeat.midi.parser import inspect_midi
from bouncebeat.midi.sequencer import NoteSequencer
from bouncebeat.models.enums import MidiMappingMode
from bouncebeat.models.events import NoteEvent
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.models.scene import BallObject, MidiPlaybackSettings, PortalObject, WallObject
from bouncebeat.simulation.engine import SimulationEngine


def _midi_collision_project(path: Path, mapping: MidiMappingMode) -> tuple[BounceBeatProject, BallObject, WallObject]:
    project = BounceBeatProject(name="Audio Collision Audit")
    project.scene.physics.gravity = (0.0, 0.0)
    project.scene.physics.air_resistance = 1.0
    project.scene.physics.world_boundaries = False
    project.midi_asset = inspect_midi(path)
    project.selected_track_ids = ["track_1", "track_2"]
    project.midi_playback.mapping_mode = mapping
    project.midi_playback.collision_cooldown_ms = 0
    ball = BallObject(
        id="audio_ball",
        midi_track_ids=["track_1"],
        midi_channel=7,
        midi_trigger=True,
        collision_cooldown_ms=0,
        particles_enabled=False,
        trail_enabled=False,
    )
    wall = WallObject(
        id="audio_wall",
        midi_track_ids=["track_2"],
        midi_channel=11,
        midi_trigger=True,
    )
    project.scene.extend([ball, wall])
    return project, ball, wall


def test_surface_midi_trigger_can_disable_notes_without_disabling_collision(demo_midi_path):
    project, ball, wall = _midi_collision_project(demo_midi_path, MidiMappingMode.PER_SURFACE)
    wall.midi_trigger = False
    engine = SimulationEngine(project, force_fallback=True)
    backend = engine._backend
    backend._register_collision(engine.models[ball.id], engine.models[wall.id], (10.0, 10.0), 700.0)
    assert engine.snapshot().collision_count == 1
    assert engine.note_events == []


def test_per_ball_and_per_surface_channel_overrides_are_applied(demo_midi_path):
    project, ball, wall = _midi_collision_project(demo_midi_path, MidiMappingMode.PER_BALL)
    engine = SimulationEngine(project, force_fallback=True)
    engine._backend._register_collision(engine.models[ball.id], engine.models[wall.id], (10.0, 10.0), 700.0)
    assert engine.note_events
    assert {event.track_id for event in engine.note_events} == {"track_1"}
    assert {event.channel for event in engine.note_events} == {7}

    project, ball, wall = _midi_collision_project(demo_midi_path, MidiMappingMode.PER_SURFACE)
    engine = SimulationEngine(project, force_fallback=True)
    engine._backend._register_collision(engine.models[ball.id], engine.models[wall.id], (10.0, 10.0), 700.0)
    assert engine.note_events
    assert {event.track_id for event in engine.note_events} == {"track_2"}
    assert {event.channel for event in engine.note_events} == {11}


def test_portals_trigger_audio_and_can_reset_velocity(demo_midi_path):
    project = BounceBeatProject(name="Portal Audio")
    project.scene.physics.gravity = (0.0, 0.0)
    project.scene.physics.world_boundaries = False
    project.midi_asset = inspect_midi(demo_midi_path)
    project.selected_track_ids = ["track_1"]
    project.midi_playback.mapping_mode = MidiMappingMode.PER_BALL
    ball = BallObject(
        id="portal_ball",
        position=(100.0, 100.0),
        initial_velocity=(500.0, 0.0),
        midi_track_ids=["track_1"],
        collision_cooldown_ms=0,
        particles_enabled=False,
        trail_enabled=False,
    )
    first = PortalObject(
        id="portal_a", position=(120.0, 100.0), target_portal_id="portal_b",
        preserve_velocity=False, midi_trigger=True,
    )
    second = PortalObject(id="portal_b", position=(500.0, 500.0), target_portal_id="portal_a")
    project.scene.extend([ball, first, second])
    engine = SimulationEngine(project, force_fallback=True)
    backend = engine._backend
    runtime_ball = engine.models[ball.id]
    state = engine.snapshot().object_states[ball.id]
    backend._teleport_fallback(runtime_ball, state, engine.models[first.id])
    assert engine.note_events
    assert state.velocity == (0.0, 0.0)
    assert engine.snapshot().collision_count == 1
    assert any(event.event_type == "portal" for event in engine.physics_events)


def test_timeline_sync_handles_multiple_loop_crossings_in_one_step(demo_midi_path):
    asset = inspect_midi(demo_midi_path)
    settings = MidiPlaybackSettings(mapping_mode=MidiMappingMode.TIMELINE_SYNCHRONIZED, loop=True)
    sequencer = NoteSequencer(asset, ["track_1", "track_2"], settings, seed=77)
    events = sequencer.timeline_events_due(0.9, 3.1)
    assert len(events) == 13
    assert [event.time for event in events] == sorted(event.time for event in events)
    assert {round(event.time, 6) for event in events} == {1.0, 1.5, 2.0, 2.5, 3.0}


def test_track_position_settings_are_honored_on_engine_reset(demo_midi_path):
    def pitches_after_reset(continue_position: bool, restart_on_reset: bool) -> list[int]:
        project, ball, _wall = _midi_collision_project(demo_midi_path, MidiMappingMode.SEQUENTIAL)
        project.selected_track_ids = ["track_1"]
        project.midi_playback.continue_position = continue_position
        project.midi_playback.restart_on_simulation_restart = restart_on_reset
        engine = SimulationEngine(project, force_fallback=True)
        engine._backend.sequencer.trigger(0.0, object_track_ids=["track_1"])
        engine.reset()
        return [event.pitch for event in engine._backend.sequencer.trigger(0.0, object_track_ids=["track_1"])]

    assert pitches_after_reset(False, True) == [60, 64]
    assert pitches_after_reset(True, True) == [67]
    assert pitches_after_reset(False, False) == [67]


def test_external_synth_wav_is_conformed_to_exact_stereo_duration(tmp_path):
    path = tmp_path / "short_mono.wav"
    sf.write(path, np.ones(1000, dtype=np.float32) * 0.1, 4000)
    _conform_wav_duration(path, duration=1.0, sample_rate=8000)
    data, rate = sf.read(path, always_2d=True)
    assert rate == 8000
    assert data.shape == (8000, 2)
    assert np.isfinite(data).all()


def test_render_midi_does_not_end_overlapping_equal_pitch_early(tmp_path):
    first = NoteEvent(0.0, 60, 100, 1.0, "track", 0, 0)
    second = NoteEvent(0.5, 60, 90, 1.0, "track", 0, 0)
    path = tmp_path / "overlap.mid"
    _write_event_midi([first, second], path)
    midi = mido.MidiFile(path)
    absolute = 0
    note_ons: list[int] = []
    note_offs: list[int] = []
    for message in midi.tracks[0]:
        absolute += message.time
        if message.type == "note_on" and message.velocity > 0:
            note_ons.append(absolute)
        elif message.type == "note_off" or (message.type == "note_on" and message.velocity == 0):
            note_offs.append(absolute)
    assert len(note_ons) == 2
    assert len(note_offs) == 1
    assert note_offs[0] == round(mido.second2tick(1.5, midi.ticks_per_beat, 500_000))


def test_master_volume_is_applied_linearly_by_fallback_renderers():
    event = NoteEvent(0.0, 69, 80, 0.2, "track", 0, 0)
    loud = render_fallback_audio([event], 0.3, sample_rate=8000, master_volume=1.0)
    quiet = render_fallback_audio([event], 0.3, sample_rate=8000, master_volume=0.5)
    loud_peak = float(np.max(np.abs(loud)))
    quiet_peak = float(np.max(np.abs(quiet)))
    assert math.isclose(quiet_peak / loud_peak, 0.5, rel_tol=0.02)

    loud_synth = PolySynth(sample_rate=8000)
    quiet_synth = PolySynth(sample_rate=8000)
    loud_synth.master_volume = 1.0
    quiet_synth.master_volume = 0.5
    loud_synth.note_on(69, 80, 0.2)
    quiet_synth.note_on(69, 80, 0.2)
    loud_block = loud_synth.render(1000)
    quiet_block = quiet_synth.render(1000)
    assert math.isclose(
        float(np.max(np.abs(quiet_block))) / float(np.max(np.abs(loud_block))),
        0.5,
        rel_tol=0.02,
    )


def test_native_backend_defers_removal_while_space_is_locked():
    import bouncebeat.simulation.engine as engine_module

    backend = object.__new__(engine_module._PymunkBackend)
    backend._space_stepping = True
    backend._pending_removals = set()
    backend._remove_pymunk_object("breakable")
    assert backend._pending_removals == {"breakable"}


def test_every_builtin_preset_remains_finite_under_extended_simulation():
    from bouncebeat.models.scene import BallObject
    from bouncebeat.presets.builtin import PRESET_NAMES, create_preset

    for name in PRESET_NAMES:
        project = create_preset(name)


        project.scene.physics.max_balls = min(project.scene.physics.max_balls, 300)
        engine = SimulationEngine(project, force_fallback=True)
        for _ in range(720):
            snapshot = engine.step()
        assert snapshot.active_ball_count <= project.scene.physics.max_balls, name
        for state in snapshot.object_states.values():
            values = (*state.position, *state.velocity, state.rotation, state.radius)
            assert all(math.isfinite(value) for value in values), name


def test_collision_to_note_to_wav_pipeline_is_complete(demo_midi_path, tmp_path):
    from bouncebeat.audio.offline import render_note_events_to_wav
    from bouncebeat.presets.builtin import create_preset

    project = create_preset("Classic Bounce")
    project.midi_asset = inspect_midi(demo_midi_path)
    project.selected_track_ids = ["track_1", "track_2"]
    project.midi_playback.mapping_mode = MidiMappingMode.LAYERED
    project.midi_playback.collision_cooldown_ms = 0
    for model in project.scene.objects:
        if isinstance(model, BallObject):
            model.midi_trigger = True
            model.collision_cooldown_ms = 0
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(900):
        engine.step()
        if len(engine.note_events) >= 6:
            break
    assert engine.snapshot().collision_count > 0
    assert engine.note_events
    duration = max(1.0, engine.time + 0.25)
    path = render_note_events_to_wav(
        engine.note_events,
        duration,
        tmp_path / "collision-audio.wav",
        sample_rate=8000,
        master_volume=0.75,
    )
    audio, sample_rate = sf.read(path, always_2d=True)
    assert sample_rate == 8000
    assert len(audio) == round(duration * sample_rate)
    assert float(np.max(np.abs(audio))) > 0.0
