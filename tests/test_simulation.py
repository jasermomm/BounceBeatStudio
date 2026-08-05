from __future__ import annotations

import copy

from bouncebeat.models.enums import DuplicationTrigger
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.models.scene import BallObject
from bouncebeat.simulation.engine import SimulationEngine


def make_project() -> tuple[BounceBeatProject, BallObject]:
    project = BounceBeatProject(name="Simulation Test")
    project.scene.logical_width = 320
    project.scene.logical_height = 240
    project.scene.physics.gravity = (0.0, 0.0)
    project.scene.physics.air_resistance = 1.0
    project.scene.physics.physics_hz = 120
    ball = BallObject(
        id="ball_test",
        position=(30.0, 120.0),
        radius=12,
        initial_velocity=(-180.0, 0.0),
        restitution=1.0,
        collision_cooldown_ms=80,
        midi_trigger=False,
        particles_enabled=False,
        trail_enabled=False,
    )
    project.scene.add(ball)
    return project, ball


def test_collision_cooldown():
    project, _ = make_project()
    engine = SimulationEngine(project, force_fallback=True)
    ball = engine.models["ball_test"]
    backend = engine._backend
    backend._register_collision(ball, None, (0.0, 0.0), 500.0)
    backend._register_collision(ball, None, (0.0, 0.0), 500.0)
    assert engine.snapshot().collision_count == 1
    backend.time = 0.081
    backend._register_collision(ball, None, (0.0, 0.0), 500.0)
    assert engine.snapshot().collision_count == 2


def test_duplication_limits_are_enforced():
    project, ball = make_project()
    project.scene.physics.max_balls = 3
    ball.duplication_trigger = DuplicationTrigger.EVERY_COLLISION
    ball.max_duplicates = 10
    ball.max_generation = 5
    engine = SimulationEngine(project, force_fallback=True)
    runtime_ball = engine.models["ball_test"]
    backend = engine._backend
    for index in range(8):
        backend.time = index * 0.2
        backend._register_collision(runtime_ball, None, (0.0, 0.0), 600.0)
    assert engine.snapshot().active_ball_count == 3


def test_deterministic_simulation_with_fixed_seed():
    project, _ = make_project()
    first = SimulationEngine(copy.deepcopy(project), force_fallback=True)
    second = SimulationEngine(copy.deepcopy(project), force_fallback=True)
    for _ in range(240):
        first.step()
        second.step()
    a = first.snapshot()
    b = second.snapshot()
    assert a.time == b.time
    assert a.collision_count == b.collision_count
    assert a.object_states["ball_test"].position == b.object_states["ball_test"].position
    assert a.object_states["ball_test"].velocity == b.object_states["ball_test"].velocity


def test_render_fps_does_not_change_fixed_physics_rate():
    project, _ = make_project()
    project.render.fps = 24
    first = SimulationEngine(copy.deepcopy(project), force_fallback=True)
    project.render.fps = 120
    second = SimulationEngine(copy.deepcopy(project), force_fallback=True)
    assert first.fixed_dt == second.fixed_dt == 1 / 120


def test_interval_duplication_is_deterministic_and_limited():
    project, ball = make_project()
    project.scene.physics.max_balls = 4
    ball.initial_velocity = (0.0, 0.0)
    ball.duplication_trigger = DuplicationTrigger.INTERVAL
    ball.duplication_interval_seconds = 0.05
    ball.max_duplicates = 10
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(30):
        engine.step()
    assert engine.snapshot().active_ball_count == 4


def test_wraparound_moves_ball_to_opposite_edge():
    project, ball = make_project()
    project.scene.physics.wraparound = True
    project.scene.physics.world_boundaries = False
    ball.position = (315.0, 120.0)
    ball.initial_velocity = (240.0, 0.0)
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(5):
        engine.step()
    x, _ = engine.snapshot().object_states[ball.id].position
    assert 0.0 <= x < project.scene.logical_width
    assert x < 30.0


def test_collision_strength_drives_independent_visual_pulses():
    project, _ = make_project()
    project.midi_playback.strength_controls_glow = True
    project.midi_playback.strength_controls_size = False
    engine = SimulationEngine(project, force_fallback=True)
    ball = engine.models["ball_test"]
    backend = engine._backend
    backend._visual_collision(ball, (10.0, 10.0), 1000.0)
    state = engine.snapshot().object_states[ball.id]
    assert state.glow_pulse > state.size_pulse
    assert state.size_pulse == 1.0


def test_track_color_mode_is_stable_across_backends():
    from bouncebeat.models.enums import ColorMode

    project, ball = make_project()
    project.scene.palette.colors = ["#111111", "#222222", "#333333", "#444444"]
    ball.color_mode = ColorMode.TRACK
    ball.midi_track_ids = ["track_piano"]
    first = SimulationEngine(copy.deepcopy(project), force_fallback=True)
    second = SimulationEngine(copy.deepcopy(project), force_fallback=True)
    a = first._backend._color_for(first.models[ball.id], track_id="track_piano")
    b = second._backend._color_for(second.models[ball.id], track_id="track_piano")
    assert a == b
    assert a in project.scene.palette.colors


def test_collision_strength_color_mode_uses_palette_range():
    from bouncebeat.models.enums import ColorMode

    project, ball = make_project()
    project.scene.palette.colors = ["#111111", "#222222", "#333333"]
    ball.color_mode = ColorMode.COLLISION_STRENGTH
    engine = SimulationEngine(project, force_fallback=True)
    runtime = engine.models[ball.id]
    assert engine._backend._color_for(runtime, strength=0) == "#111111"
    assert engine._backend._color_for(runtime, strength=1799) == "#333333"


def test_duplication_and_lifetime_emit_timeline_events():
    project, ball = make_project()
    ball.duplication_trigger = DuplicationTrigger.INTERVAL
    ball.duplication_interval_seconds = 0.02
    ball.max_duplicates = 1
    ball.lifetime_seconds = 0.06
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(20):
        engine.step()
    event_types = [event.event_type for event in engine.physics_events]
    assert "ball_creation" in event_types
    assert "ball_deletion" in event_types
