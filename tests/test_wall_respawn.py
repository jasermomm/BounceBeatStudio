from __future__ import annotations

import math

from bouncebeat.models.enums import (
    DuplicationMode,
    DuplicationSpawnMode,
    DuplicationTrigger,
    DuplicationVelocityMode,
)
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.models.scene import BallObject, BumperObject, RingObject, WallObject
from bouncebeat.presets.builtin import create_preset
from bouncebeat.simulation.engine import SimulationEngine


def respawn_project(*, world_boundaries: bool = False) -> tuple[BounceBeatProject, BallObject, RingObject, WallObject]:
    project = BounceBeatProject(name="Wall Respawn")
    project.scene.logical_width = 400
    project.scene.logical_height = 300
    project.scene.physics.gravity = (0.0, 0.0)
    project.scene.physics.air_resistance = 1.0
    project.scene.physics.world_boundaries = world_boundaries
    project.scene.physics.maximum_speed = 5000.0
    project.scene.physics.max_balls = 1
    project.midi_playback.collision_cooldown_ms = 0

    ring = RingObject(
        id="ring",
        name="Spawn Ring",
        position=(200.0, 150.0),
        radius=75.0,
        thickness=10.0,
        opening_angle=45.0,
    )
    wall = WallObject(
        id="wall",
        name="Outer Wall",
        start=(360.0, 30.0),
        end=(360.0, 270.0),
        thickness=12.0,
        restitution=1.0,
    )
    ball = BallObject(
        id="ball",
        name="Escape Ball",
        position=(320.0, 150.0),
        radius=10.0,
        initial_velocity=(900.0, 0.0),
        maximum_speed=5000.0,
        restitution=1.0,
        midi_trigger=False,
        particles_enabled=False,
        trail_enabled=False,
        collision_cooldown_ms=0,
        duplication_trigger=DuplicationTrigger.ANY_WALL,
        duplication_mode=DuplicationMode.EXACT,
        duplication_spawn_mode=DuplicationSpawnMode.SELECTED_OBJECT_CENTER,
        duplication_spawn_target_id=ring.id,
        duplication_spawn_spread=0.0,
        duplication_velocity_mode=DuplicationVelocityMode.INITIAL,
        remove_source_after_duplication=True,
        reset_generation_on_respawn=True,
        max_duplicates=1,
        max_generation=1,
    )
    project.scene.extend([ring, wall, ball])
    return project, ball, ring, wall


def test_any_wall_respawns_inside_selected_ring_and_removes_source():
    project, ball, ring, _ = respawn_project()
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(20):
        engine.step()
        if ball.id not in engine.models:
            break

    balls = [model for model in engine.models.values() if isinstance(model, BallObject)]
    assert len(balls) == 1
    replacement = balls[0]
    assert replacement.id != ball.id
    assert ball.id not in engine.models
    state = engine.snapshot().object_states[replacement.id]
    assert math.dist(state.position, ring.position) < 10.0
    creation = next(event for event in engine.physics_events if event.event_type == "ball_creation" and event.object_b == ball.id)
    assert creation.position == ring.position
    assert state.velocity == ball.initial_velocity
    assert replacement.generation == 0
    assert any(event.event_type == "ball_deletion" and event.object_a == ball.id for event in engine.physics_events)


def test_any_wall_does_not_trigger_on_ring_or_bumper():
    project, ball, ring, _ = respawn_project()
    bumper = BumperObject(id="bumper", position=(250.0, 150.0), radius=20.0)
    project.scene.add(bumper)
    engine = SimulationEngine(project, force_fallback=True)
    runtime_ball = engine.models[ball.id]
    backend = engine._backend

    backend._register_collision(runtime_ball, ring, ring.position, 500.0)
    backend.time += 0.1
    backend._register_collision(runtime_ball, bumper, bumper.position, 500.0)
    backend._flush_pending_removals()

    assert engine.snapshot().active_ball_count == 1
    assert ball.id in engine.models
    assert not any(event.event_type == "ball_creation" for event in engine.physics_events)


def test_any_wall_includes_implicit_world_boundaries():
    project, ball, ring, wall = respawn_project(world_boundaries=True)
    project.scene.remove(wall.id)
    ball.position = (385.0, 150.0)
    ball.initial_velocity = (900.0, 0.0)
    engine = SimulationEngine(project, force_fallback=True)

    for _ in range(8):
        engine.step()
        if ball.id not in engine.models:
            break

    balls = [model for model in engine.models.values() if isinstance(model, BallObject)]
    assert len(balls) == 1
    assert balls[0].id != ball.id
    creation = next(event for event in engine.physics_events if event.event_type == "ball_creation")
    assert creation.position == ring.position
    assert math.dist(engine.snapshot().object_states[balls[0].id].position, ring.position) < 10.0


def test_spawn_spread_is_clamped_inside_selected_ring():
    project, ball, ring, _ = respawn_project()
    ball.remove_source_after_duplication = False
    ball.duplication_spawn_spread = 10000.0
    project.scene.physics.max_balls = 2
    engine = SimulationEngine(project, force_fallback=True)
    backend = engine._backend
    runtime_ball = engine.models[ball.id]
    wall = engine.models["wall"]
    backend._register_collision(runtime_ball, wall, (360.0, 150.0), 500.0)

    replacement = next(model for model in engine.models.values() if isinstance(model, BallObject) and model.id != ball.id)
    distance = math.dist(engine.snapshot().object_states[replacement.id].position, ring.position)
    safe_radius = ring.radius - ring.thickness / 2.0 - replacement.radius - 4.0
    assert distance <= safe_radius + 1e-9


def test_respawn_settings_round_trip_through_project_serialization():
    project, ball, _, _ = respawn_project()
    restored = BounceBeatProject.from_dict(project.to_dict())
    restored_ball = restored.scene.get(ball.id)
    assert isinstance(restored_ball, BallObject)
    assert restored_ball.duplication_trigger == DuplicationTrigger.ANY_WALL
    assert restored_ball.duplication_spawn_mode == DuplicationSpawnMode.SELECTED_OBJECT_CENTER
    assert restored_ball.duplication_velocity_mode == DuplicationVelocityMode.INITIAL
    assert restored_ball.duplication_spawn_target_id == "ring"
    assert restored_ball.remove_source_after_duplication is True
    assert restored_ball.reset_generation_on_respawn is True


def test_escape_and_respawn_preset_is_ready_to_use():
    project = create_preset("Escape and Respawn")
    walls = [obj for obj in project.scene.objects if isinstance(obj, WallObject)]
    rings = [obj for obj in project.scene.objects if isinstance(obj, RingObject)]
    balls = [obj for obj in project.scene.objects if isinstance(obj, BallObject)]
    assert len(walls) == 4
    assert len(rings) == 1
    assert len(balls) == 1
    ball = balls[0]
    assert ball.duplication_trigger == DuplicationTrigger.ANY_WALL
    assert ball.duplication_spawn_target_id == rings[0].id
    assert ball.remove_source_after_duplication is True


def test_pymunk_wall_respawn_creation_is_deferred_until_space_unlocks(monkeypatch):
    from collections import defaultdict

    import bouncebeat.simulation.engine as engine_module

    project, ball, _, wall = respawn_project()
    backend = object.__new__(engine_module._PymunkBackend)
    backend.project = project
    backend.models = {ball.id: ball, wall.id: wall}
    backend._duplicate_counts = defaultdict(int)
    backend._pending_duplicate_ids = set()
    backend._space_stepping = True

    backend._maybe_duplicate(ball, wall, 500.0, [])
    assert backend._pending_duplicate_ids == {ball.id}

    performed: list[str] = []
    monkeypatch.setattr(
        engine_module._BackendBase,
        "_attempt_duplicate",
        lambda self, queued_ball: performed.append(queued_ball.id) or True,
    )
    backend._space_stepping = False
    backend._flush_pending_duplications()

    assert performed == [ball.id]
    assert backend._pending_duplicate_ids == set()


def test_respawn_settings_survive_bouncebeat_file_save_and_reopen(tmp_path):
    from bouncebeat.projects.serializer import load_project, save_project

    project, ball, _, _ = respawn_project()
    path = save_project(project, tmp_path / "wall-respawn.bouncebeat")
    reopened = load_project(path)
    reopened_ball = reopened.scene.get(ball.id)

    assert isinstance(reopened_ball, BallObject)
    assert reopened_ball.duplication_trigger == DuplicationTrigger.ANY_WALL
    assert reopened_ball.duplication_spawn_mode == DuplicationSpawnMode.SELECTED_OBJECT_CENTER
    assert reopened_ball.duplication_spawn_target_id == "ring"
    assert reopened_ball.duplication_velocity_mode == DuplicationVelocityMode.INITIAL
    assert reopened_ball.remove_source_after_duplication is True


def test_native_pymunk_wall_respawn_when_available():
    import pytest
    import bouncebeat.simulation.engine as engine_module

    if engine_module.pymunk is None:
        pytest.skip("Pymunk binary wheel is not installed in this validation container")

    project, ball, ring, _ = respawn_project()
    engine = SimulationEngine(project, force_fallback=False)
    for _ in range(30):
        engine.step()
        if ball.id not in engine.models:
            break

    balls = [model for model in engine.models.values() if isinstance(model, BallObject)]
    assert len(balls) == 1
    assert balls[0].id != ball.id
    assert math.dist(engine.snapshot().object_states[balls[0].id].position, ring.position) < 20.0


def _kill_all_current_balls(engine: SimulationEngine, wall_id: str = "wall") -> None:
    """Trigger one wall-death event for every ball alive at call time."""
    backend = engine._backend
    wall = engine.models[wall_id]
    current = [model for model in list(engine.models.values()) if isinstance(model, BallObject)]
    for runtime_ball in current:
        backend.time += 0.001
        backend._register_collision(runtime_ball, wall, wall.position, 500.0)
        backend._flush_pending_removals()


def test_configurable_death_batch_can_spawn_three_then_nine():
    project, ball, ring, _ = respawn_project()
    project.scene.physics.max_balls = 100
    ball.duplication_spawn_count = 3
    ball.duplication_spawn_spread = 60.0
    engine = SimulationEngine(project, force_fallback=True)

    _kill_all_current_balls(engine)
    first_generation = [model for model in engine.models.values() if isinstance(model, BallObject)]
    assert len(first_generation) == 3
    assert all(model.duplication_spawn_count == 3 for model in first_generation)
    assert all(model.generation == 0 for model in first_generation)
    assert all(
        math.dist(engine.snapshot().object_states[model.id].position, ring.position) <= 60.0 + 1e-9
        for model in first_generation
    )

    _kill_all_current_balls(engine)
    second_generation = [model for model in engine.models.values() if isinstance(model, BallObject)]
    assert len(second_generation) == 9
    creation_events = [event for event in engine.physics_events if event.event_type == "ball_creation"]
    assert len(creation_events) == 12
    assert {event.payload["requested_count"] for event in creation_events} == {3}


def test_death_batch_count_one_preserves_normal_respawn():
    project, ball, _, _ = respawn_project()
    project.scene.physics.max_balls = 100
    ball.duplication_spawn_count = 1
    engine = SimulationEngine(project, force_fallback=True)

    _kill_all_current_balls(engine)
    balls = [model for model in engine.models.values() if isinstance(model, BallObject)]
    assert len(balls) == 1
    assert balls[0].id != ball.id


def test_death_batch_is_limited_by_global_ball_cap():
    project, ball, _, _ = respawn_project()
    project.scene.physics.max_balls = 5
    ball.duplication_spawn_count = 64
    engine = SimulationEngine(project, force_fallback=True)

    _kill_all_current_balls(engine)
    balls = [model for model in engine.models.values() if isinstance(model, BallObject)]
    assert len(balls) == 5
    events = [event for event in engine.physics_events if event.event_type == "ball_creation"]
    assert len(events) == 5
    assert all(event.payload["requested_count"] == 64 for event in events)
    assert all(event.payload["created_count"] == 5 for event in events)


def test_batch_spawn_positions_are_distinct_and_deterministic():
    def positions_for_seed(seed: int) -> list[tuple[float, float]]:
        project, ball, _, _ = respawn_project()
        project.scene.physics.max_balls = 20
        project.scene.physics.deterministic_seed = seed
        ball.duplication_spawn_count = 6
        ball.duplication_spawn_spread = 60.0
        engine = SimulationEngine(project, force_fallback=True)
        _kill_all_current_balls(engine)
        return sorted(
            engine.snapshot().object_states[model.id].position
            for model in engine.models.values()
            if isinstance(model, BallObject)
        )

    first = positions_for_seed(2026)
    second = positions_for_seed(2026)
    third = positions_for_seed(2027)
    assert len(set(first)) == 6
    assert first == second
    assert first != third


def test_spawn_count_round_trips_and_old_projects_default_to_one():
    project, ball, _, _ = respawn_project()
    ball.duplication_spawn_count = 7
    restored = BounceBeatProject.from_dict(project.to_dict())
    restored_ball = restored.scene.get(ball.id)
    assert isinstance(restored_ball, BallObject)
    assert restored_ball.duplication_spawn_count == 7

    old_data = project.to_dict()
    old_ball = next(item for item in old_data["scene"]["objects"] if item["id"] == ball.id)
    old_ball.pop("duplication_spawn_count")
    old_restored = BounceBeatProject.from_dict(old_data)
    old_restored_ball = old_restored.scene.get(ball.id)
    assert isinstance(old_restored_ball, BallObject)
    assert old_restored_ball.duplication_spawn_count == 1


def test_escape_and_respawn_preset_defaults_to_three_way_chain():
    project = create_preset("Escape and Respawn")
    ball = next(obj for obj in project.scene.objects if isinstance(obj, BallObject))
    assert ball.duplication_spawn_count == 3
    assert ball.max_duplicates == 1
    assert ball.remove_source_after_duplication is True
    assert project.scene.physics.max_balls >= 243
