from bouncebeat.models.scene import BallObject, BumperObject, PortalObject, RingObject, WallObject
from bouncebeat.presets.builtin import PRESET_NAMES, create_preset


def test_new_objects_have_readable_portrait_defaults() -> None:
    assert BallObject().radius >= 48
    assert WallObject().thickness >= 16
    assert RingObject().thickness >= 18
    assert BumperObject().radius >= 64
    assert PortalObject().radius >= 58


def test_builtin_preset_balls_are_not_microscopic() -> None:
    for name in PRESET_NAMES:
        project = create_preset(name)
        balls = project.scene.balls()
        assert balls, name
        assert min(ball.radius for ball in balls) >= 44, name
