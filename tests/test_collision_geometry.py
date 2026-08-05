from __future__ import annotations

import math

import pytest

from bouncebeat.models.project import BounceBeatProject
from bouncebeat.models.scene import BallObject, BumperObject, PolygonObject, RingObject, WallObject
from bouncebeat.simulation.engine import SimulationEngine
from bouncebeat.simulation.geometry import qt_ring_arc_degrees, ring_arc_points, ring_arc_segments


def collision_project() -> BounceBeatProject:
    project = BounceBeatProject(name="Collision Geometry")
    project.scene.logical_width = 320
    project.scene.logical_height = 240
    project.scene.physics.gravity = (0.0, 0.0)
    project.scene.physics.air_resistance = 1.0
    project.scene.physics.world_boundaries = False
    project.scene.physics.maximum_speed = 10000.0
    project.scene.physics.continuous_collision_detection = True
    project.scene.physics.max_collision_substeps = 32
    project.midi_playback.collision_cooldown_ms = 0
    return project


def quiet_ball(**kwargs) -> BallObject:
    defaults = dict(
        id="ball",
        radius=8.0,
        maximum_speed=10000.0,
        restitution=1.0,
        midi_trigger=False,
        particles_enabled=False,
        trail_enabled=False,
        collision_cooldown_ms=0,
    )
    defaults.update(kwargs)
    return BallObject(**defaults)


def test_closed_ring_has_connected_wraparound_neighbors():
    segments = ring_arc_segments(100.0, 0.0, 96)
    assert len(segments) == 96
    assert segments[0].previous == segments[-1].start
    assert segments[-1].following == segments[0].end
    assert segments[-1].end == segments[0].start


def test_open_ring_endpoints_land_exactly_on_opening_boundaries():
    points, closed = ring_arc_points(100.0, 48.0, 96)
    assert not closed
    first_angle = math.degrees(math.atan2(points[0][1], points[0][0])) % 360
    last_angle = math.degrees(math.atan2(points[-1][1], points[-1][0])) % 360
    assert math.isclose(first_angle, 24.0, abs_tol=1e-9)
    assert math.isclose(last_angle, 336.0, abs_tol=1e-9)


def test_qt_arc_uses_opposite_sign_to_screen_clockwise_physics_rotation():
    start, span = qt_ring_arc_degrees(45.0, 40.0)
    assert math.isclose(start, -25.0)
    assert math.isclose(span, 320.0)


def test_fast_ball_does_not_tunnel_through_bottom_right_ring_arc():
    project = collision_project()
    center = (160.0, 120.0)
    angle = math.radians(45.0)
    ring = RingObject(
        id="ring",
        position=center,
        radius=80.0,
        thickness=8.0,
        opening_angle=40.0,
        rotation_speed=30.0,
        segments=144,
    )
    start_radius = ring.radius - 5.0 - ring.thickness / 2.0 - 2.0
    ball = quiet_ball(
        position=(center[0] + math.cos(angle) * start_radius, center[1] + math.sin(angle) * start_radius),
        radius=5.0,
        initial_velocity=(math.cos(angle) * 2500.0, math.sin(angle) * 2500.0),
    )
    project.scene.extend([ring, ball])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(6):
        engine.step()
    state = engine.snapshot().object_states[ball.id]
    assert engine.snapshot().collision_count >= 1
    assert math.dist(state.position, center) < ring.radius
    assert state.velocity[0] * math.cos(angle) + state.velocity[1] * math.sin(angle) < 0.0


def test_ball_can_escape_only_through_the_configured_opening():
    project = collision_project()
    ring = RingObject(
        id="ring",
        position=(160.0, 120.0),
        radius=80.0,
        thickness=10.0,
        opening_angle=50.0,
        rotation_speed=0.0,
        segments=120,
    )
    ball = quiet_ball(position=(210.0, 120.0), radius=5.0, initial_velocity=(1000.0, 0.0))
    project.scene.extend([ring, ball])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(10):
        engine.step()
    state = engine.snapshot().object_states[ball.id]
    assert state.position[0] > ring.position[0] + ring.radius + ball.radius
    assert engine.snapshot().collision_count == 0


def test_wall_thickness_collides_at_high_speed():
    project = collision_project()
    wall = WallObject(id="wall", start=(160.0, 30.0), end=(160.0, 210.0), thickness=10.0, restitution=1.0)
    ball = quiet_ball(position=(80.0, 120.0), radius=10.0, initial_velocity=(1200.0, 0.0))
    project.scene.extend([wall, ball])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(12):
        engine.step()
    state = engine.snapshot().object_states[ball.id]
    assert state.velocity[0] < 0.0
    assert engine.snapshot().collision_count >= 1


def test_rotating_polygon_collision_uses_live_rotation():
    project = collision_project()
    obstacle = PolygonObject(
        id="bar",
        position=(160.0, 120.0),
        vertices=[(-10.0, -80.0), (10.0, -80.0), (10.0, 80.0), (-10.0, 80.0)],
        rotation_speed=90.0,
        restitution=1.0,
    )
    ball = quiet_ball(position=(80.0, 120.0), radius=10.0, initial_velocity=(1000.0, 0.0))
    project.scene.extend([obstacle, ball])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(20):
        engine.step()
    snapshot = engine.snapshot()
    assert snapshot.object_states[obstacle.id].rotation > 0.0
    assert snapshot.object_states[ball.id].velocity[0] < 0.0
    assert snapshot.collision_count >= 1


def test_bumper_radius_and_extra_impulse_are_applied():
    project = collision_project()
    bumper = BumperObject(id="bumper", position=(160.0, 120.0), radius=30.0, restitution=1.0, impulse=300.0)
    ball = quiet_ball(position=(80.0, 120.0), radius=10.0, initial_velocity=(800.0, 0.0))
    project.scene.extend([bumper, ball])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(12):
        engine.step()
    state = engine.snapshot().object_states[ball.id]
    assert state.velocity[0] <= -1000.0
    assert engine.snapshot().collision_count >= 1


def test_ball_to_ball_collision_resolves_both_velocities():
    project = collision_project()
    first = quiet_ball(id="first", position=(110.0, 120.0), initial_velocity=(500.0, 0.0), mass=1.0)
    second = quiet_ball(id="second", position=(210.0, 120.0), initial_velocity=(-500.0, 0.0), mass=1.0)
    project.scene.extend([first, second])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(16):
        engine.step()
    snapshot = engine.snapshot()
    assert snapshot.object_states[first.id].velocity[0] < 0.0
    assert snapshot.object_states[second.id].velocity[0] > 0.0
    assert snapshot.collision_count >= 1


def test_trigger_ring_reports_contact_without_bouncing():
    project = collision_project()
    ring = RingObject(
        id="trigger_ring",
        position=(160.0, 120.0),
        radius=80.0,
        thickness=10.0,
        opening_angle=0.0,
        collision_mode="trigger",
        segments=120,
    )
    ball = quiet_ball(position=(210.0, 120.0), radius=5.0, initial_velocity=(1000.0, 0.0))
    project.scene.extend([ring, ball])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(8):
        engine.step()
    state = engine.snapshot().object_states[ball.id]
    assert state.position[0] > ring.position[0] + ring.radius + ball.radius
    assert state.velocity[0] > 0.0
    assert engine.snapshot().collision_count >= 1


def test_disabled_ring_has_no_physical_or_trigger_collision():
    project = collision_project()
    ring = RingObject(
        id="disabled_ring",
        position=(160.0, 120.0),
        radius=80.0,
        thickness=30.0,
        opening_angle=0.0,
        collision_mode="disabled",
        segments=120,
    )
    ball = quiet_ball(position=(210.0, 120.0), radius=5.0, initial_velocity=(1000.0, 0.0))
    project.scene.extend([ring, ball])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(8):
        engine.step()
    assert engine.snapshot().object_states[ball.id].velocity[0] > 0.0
    assert engine.snapshot().collision_count == 0


def test_ring_thickness_changes_the_contact_radius():
    def collision_position(thickness: float) -> float:
        project = collision_project()
        ring = RingObject(
            id="ring",
            position=(160.0, 120.0),
            radius=80.0,
            thickness=thickness,
            opening_angle=0.0,
            segments=120,
        )
        ball = quiet_ball(position=(210.0, 120.0), radius=5.0, initial_velocity=(500.0, 0.0))
        project.scene.extend([ring, ball])
        engine = SimulationEngine(project, force_fallback=True)
        while engine.snapshot().collision_count == 0 and engine.time < 0.2:
            engine.step()
        return engine.snapshot().object_states[ball.id].position[0]

    thick_contact = collision_position(30.0)
    thin_contact = collision_position(6.0)
    assert thick_contact < thin_contact


def test_breakable_wall_is_removed_after_strong_hit():
    project = collision_project()
    wall = WallObject(
        id="breakable",
        start=(160.0, 30.0),
        end=(160.0, 210.0),
        thickness=10.0,
        restitution=1.0,
        break_on_hit=True,
        break_strength=100.0,
    )
    ball = quiet_ball(position=(80.0, 120.0), radius=10.0, initial_velocity=(1200.0, 0.0))
    project.scene.extend([wall, ball])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(12):
        engine.step()
    assert wall.id not in engine.models
    assert any(event.event_type == "object_deletion" and event.object_a == wall.id for event in engine.physics_events)


def test_portal_uses_radius_and_exits_outside_target_sensor():
    from bouncebeat.models.scene import PortalObject

    project = collision_project()
    first = PortalObject(id="portal_a", position=(120.0, 120.0), radius=20.0, target_portal_id="portal_b")
    second = PortalObject(id="portal_b", position=(250.0, 120.0), radius=24.0, target_portal_id="portal_a")
    ball = quiet_ball(position=(60.0, 120.0), radius=8.0, initial_velocity=(600.0, 0.0))
    project.scene.extend([first, second, ball])
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(10):
        engine.step()
    state = engine.snapshot().object_states[ball.id]
    assert state.position[0] > second.position[0] + second.radius + ball.radius
    assert state.velocity[0] > 0.0
    assert sum(event.event_type == "portal" for event in engine.physics_events) == 1


@pytest.mark.parametrize("angle_degrees", [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0])
def test_closed_rotating_ring_has_no_escape_seam_at_any_octant(angle_degrees: float):
    project = collision_project()
    center = (160.0, 120.0)
    ring = RingObject(
        id="closed_ring",
        position=center,
        radius=82.0,
        thickness=8.0,
        opening_angle=0.0,
        rotation_speed=240.0,
        segments=144,
    )
    angle = math.radians(angle_degrees)
    ball = quiet_ball(
        position=center,
        radius=5.0,
        initial_velocity=(math.cos(angle) * 2200.0, math.sin(angle) * 2200.0),
    )
    project.scene.extend([ring, ball])
    engine = SimulationEngine(project, force_fallback=True)
    maximum_distance = 0.0
    for _ in range(120):
        engine.step()
        maximum_distance = max(
            maximum_distance,
            math.dist(engine.snapshot().object_states[ball.id].position, center),
        )
    assert engine.snapshot().collision_count >= 1
    assert maximum_distance < ring.radius + ring.thickness / 2.0 + ball.radius


def test_pymunk_ring_builder_applies_neighbors_to_every_segment(monkeypatch):
    from collections import defaultdict
    from types import SimpleNamespace

    import bouncebeat.simulation.engine as engine_module

    class FakeBody:
        KINEMATIC = 1

        def __init__(self, body_type=None):
            self.body_type = body_type
            self.position = (0.0, 0.0)
            self.angle = 0.0
            self.angular_velocity = 0.0

    class FakeSegment:
        def __init__(self, body, start, end, radius):
            self.body = body
            self.start = start
            self.end = end
            self.radius = radius
            self.neighbors = None
            self.elasticity = 0.0
            self.friction = 0.0
            self.sensor = False

        def set_neighbors(self, previous, following):
            self.neighbors = (previous, following)

    class FakeSpace:
        def __init__(self):
            self.added = []
            self.removed = []

        def add(self, *items):
            self.added.extend(items)

        def remove(self, *items):
            self.removed.extend(items)

    fake_pymunk = SimpleNamespace(Body=FakeBody, Segment=FakeSegment)
    monkeypatch.setattr(engine_module, "pymunk", fake_pymunk)
    backend = object.__new__(engine_module._PymunkBackend)
    backend.project = collision_project()
    backend.space = FakeSpace()
    backend.bodies = {}
    backend.shapes = defaultdict(list)
    backend.states = {}

    ring = RingObject(id="native_ring", position=(160.0, 120.0), radius=80.0, thickness=12.0, segments=48)
    backend._add_ring(ring)

    assert len(backend.shapes[ring.id]) == 48
    assert all(shape.neighbors is not None for shape in backend.shapes[ring.id])
    first = backend.shapes[ring.id][0]
    last = backend.shapes[ring.id][-1]
    assert first.neighbors[0] == last.start
    assert last.neighbors[1] == first.end


def test_pymunk_expanding_ring_rebuild_preserves_live_angle(monkeypatch):
    from collections import defaultdict
    from types import SimpleNamespace

    import bouncebeat.simulation.engine as engine_module

    class FakeBody:
        KINEMATIC = 1

        def __init__(self, body_type=None):
            self.body_type = body_type
            self.position = (0.0, 0.0)
            self.angle = 0.0
            self.angular_velocity = 0.0

    class FakeSegment:
        def __init__(self, body, start, end, radius):
            self.body = body
            self.start = start
            self.end = end
            self.radius = radius
            self.elasticity = 0.0
            self.friction = 0.0
            self.sensor = False

        def set_neighbors(self, previous, following):
            self.neighbors = (previous, following)

    class FakeSpace:
        def add(self, *items):
            pass

        def remove(self, *items):
            pass

    monkeypatch.setattr(engine_module, "pymunk", SimpleNamespace(Body=FakeBody, Segment=FakeSegment))
    backend = object.__new__(engine_module._PymunkBackend)
    backend.project = collision_project()
    backend.space = FakeSpace()
    backend.bodies = {}
    backend.shapes = defaultdict(list)
    backend.states = {}

    ring = RingObject(id="expanding", position=(160.0, 120.0), radius=80.0, thickness=12.0, rotation_speed=90.0)
    backend._add_ring(ring)
    backend.bodies[ring.id].angle = 1.234
    backend.bodies[ring.id].angular_velocity = 2.345
    ring.radius = 95.0
    backend._rebuild_ring(ring)

    assert math.isclose(backend.bodies[ring.id].angle, 1.234)
    assert math.isclose(backend.bodies[ring.id].angular_velocity, 2.345)
    assert backend.states[ring.id].radius == 95.0
