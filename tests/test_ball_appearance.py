from __future__ import annotations

import copy

import pytest

from bouncebeat.models.enums import BallAppearance
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.models.scene import BallObject
from bouncebeat.simulation.engine import SimulationEngine


def _appearance_project() -> tuple[BounceBeatProject, BallObject]:
    project = BounceBeatProject(name="Ball Appearance")
    project.scene.logical_width = 320
    project.scene.logical_height = 240
    project.scene.physics.gravity = (0.0, 0.0)
    project.scene.physics.air_resistance = 1.0
    project.scene.physics.world_boundaries = False
    ball = BallObject(
        id="appearance_ball",
        position=(160.0, 120.0),
        radius=48.0,
        initial_velocity=(120.0, -40.0),
        color="#26D9FF",
        particles_enabled=False,
        trail_enabled=False,
        midi_trigger=False,
    )
    project.scene.add(ball)
    return project, ball


def test_ball_appearance_round_trips_and_old_projects_keep_glossy_default():
    project, ball = _appearance_project()
    ball.appearance = BallAppearance.FLAT
    ball.reflections_enabled = False
    ball.reflection_strength = 0.22
    ball.reflection_size = 0.31
    ball.reflection_offset = (0.2, -0.1)
    ball.shading_strength = 0.0
    ball.outline_enabled = False

    restored = BounceBeatProject.from_dict(project.to_dict())
    restored_ball = restored.scene.get(ball.id)
    assert isinstance(restored_ball, BallObject)
    assert restored_ball.appearance == BallAppearance.FLAT
    assert restored_ball.reflections_enabled is False
    assert restored_ball.reflection_offset == (0.2, -0.1)
    assert restored_ball.outline_enabled is False

    old_data = project.to_dict()
    old_ball = next(item for item in old_data["scene"]["objects"] if item["id"] == ball.id)
    for key in (
        "appearance",
        "reflections_enabled",
        "reflection_strength",
        "reflection_size",
        "reflection_offset",
        "shading_strength",
        "outline_enabled",
        "outline_color",
        "outline_opacity",
        "outline_width",
    ):
        old_ball.pop(key, None)
    old_restored = BounceBeatProject.from_dict(old_data)
    old_restored_ball = old_restored.scene.get(ball.id)
    assert isinstance(old_restored_ball, BallObject)
    assert old_restored_ball.appearance == BallAppearance.GLOSSY
    assert old_restored_ball.reflections_enabled is True


def test_ball_appearance_never_changes_physics_output():
    project, ball = _appearance_project()
    flat_project = copy.deepcopy(project)
    glossy_project = copy.deepcopy(project)
    flat_ball = flat_project.scene.get(ball.id)
    glossy_ball = glossy_project.scene.get(ball.id)
    assert isinstance(flat_ball, BallObject)
    assert isinstance(glossy_ball, BallObject)
    flat_ball.appearance = BallAppearance.FLAT
    flat_ball.reflections_enabled = False
    glossy_ball.appearance = BallAppearance.GLOSSY
    glossy_ball.reflections_enabled = True

    flat_engine = SimulationEngine(flat_project, force_fallback=True)
    glossy_engine = SimulationEngine(glossy_project, force_fallback=True)
    for _ in range(180):
        flat_engine.step()
        glossy_engine.step()
    flat_state = flat_engine.snapshot().object_states[ball.id]
    glossy_state = glossy_engine.snapshot().object_states[ball.id]
    assert flat_state.position == glossy_state.position
    assert flat_state.velocity == glossy_state.velocity
    assert flat_engine.snapshot().collision_count == glossy_engine.snapshot().collision_count


def test_qt_renderer_visibly_distinguishes_flat_and_glossy_styles():
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QGuiApplication
    from bouncebeat.rendering.qt_renderer import SceneRenderer

    application = QGuiApplication.instance() or QGuiApplication([])
    flat_project, flat_ball = _appearance_project()
    flat_ball.appearance = BallAppearance.FLAT
    flat_ball.reflections_enabled = False
    flat_ball.outline_enabled = False
    flat_engine = SimulationEngine(flat_project, force_fallback=True)

    glossy_project, glossy_ball = _appearance_project()
    glossy_ball.appearance = BallAppearance.GLOSSY
    glossy_ball.reflections_enabled = True
    glossy_ball.outline_enabled = True
    glossy_engine = SimulationEngine(glossy_project, force_fallback=True)

    renderer = SceneRenderer()
    flat = renderer.render(
        flat_project, flat_engine.snapshot(), flat_engine.models, 320, 240, show_stats=False
    )
    glossy = renderer.render(
        glossy_project, glossy_engine.snapshot(), glossy_engine.models, 320, 240, show_stats=False
    )

    assert flat.sizeInBytes() == glossy.sizeInBytes()
    assert bytes(flat.bits()) != bytes(glossy.bits())
    _ = application


def test_duplicated_balls_inherit_appearance_controls():
    from bouncebeat.models.enums import DuplicationTrigger

    project, ball = _appearance_project()
    project.scene.physics.max_balls = 3
    ball.appearance = BallAppearance.NEON
    ball.reflections_enabled = False
    ball.outline_color = "#FF00AA"
    ball.duplication_trigger = DuplicationTrigger.INTERVAL
    ball.duplication_interval_seconds = 0.01
    ball.max_duplicates = 1
    ball.max_generation = 1
    engine = SimulationEngine(project, force_fallback=True)
    for _ in range(5):
        engine.step()
    children = [model for model in engine.models.values() if isinstance(model, BallObject) and model.id != ball.id]
    assert len(children) == 1
    assert children[0].appearance == BallAppearance.NEON
    assert children[0].reflections_enabled is False
    assert children[0].outline_color == "#FF00AA"
