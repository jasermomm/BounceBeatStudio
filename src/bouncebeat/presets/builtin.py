from __future__ import annotations

import json
from pathlib import Path

from bouncebeat.models.enums import (
    ColorMode, DuplicationMode, DuplicationSpawnMode, DuplicationTrigger,
    DuplicationVelocityMode, MidiMappingMode,
)
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.models.scene import (
    BallObject,
    BumperObject,
    EmitterObject,
    PolygonObject,
    PortalObject,
    RingObject,
    TextOverlayObject,
    WallObject,
)
from bouncebeat.utilities.paths import resource_path

PRESET_NAMES = [
    "Classic Bounce",
    "Circular Escape",
    "Escape and Respawn",
    "Duplicate on Bounce",
    "Multi-Instrument Orchestra",
    "Expanding Rings",
    "Color Explosion",
    "Obstacle Course",
    "Music Visualizer",
]

PALETTE = ["#FF4D6D", "#FFD166", "#06D6A0", "#118AB2", "#8338EC"]


def _base(name: str) -> BounceBeatProject:
    project = BounceBeatProject(name=name, preset_name=name)
    project.scene.palette.colors = list(PALETTE)
    project.scene.palette.mode = ColorMode.CYCLE
    project.scene.physics.gravity = (0.0, 620.0)
    project.scene.physics.deterministic_seed = 1337
    project.render.width = 1080
    project.render.height = 1920
    project.render.fps = 60
    project.recording.duration_seconds = 30.0
    return project


def _arena(project: BounceBeatProject, margin: float = 90.0) -> None:
    w, h = project.scene.logical_width, project.scene.logical_height
    walls = [
        WallObject(name="Top Wall", start=(margin, margin), end=(w - margin, margin), color="#64748B"),
        WallObject(name="Right Wall", start=(w - margin, margin), end=(w - margin, h - margin), color="#64748B"),
        WallObject(name="Bottom Wall", start=(w - margin, h - margin), end=(margin, h - margin), color="#64748B"),
        WallObject(name="Left Wall", start=(margin, h - margin), end=(margin, margin), color="#64748B"),
    ]
    project.scene.extend(walls)


def classic_bounce() -> BounceBeatProject:
    project = _base("Classic Bounce")
    project.scene.physics.gravity = (0.0, 430.0)
    _arena(project)
    project.scene.add(BallObject(name="Melody Ball", position=(540, 500), initial_velocity=(390, -50), radius=52, color=PALETTE[0]))
    return project


def circular_escape() -> BounceBeatProject:
    project = _base("Circular Escape")
    project.scene.physics.gravity = (0.0, 360.0)
    project.scene.physics.substeps = 2
    project.scene.physics.max_collision_substeps = 24
    project.scene.physics.collision_iterations = 20
    project.scene.add(RingObject(name="Rotating Escape Ring", position=(540, 960), radius=430, thickness=24, opening_angle=48, rotation_speed=32, segments=180, color=PALETTE[4], glow=0.7))
    project.scene.add(BallObject(name="Escape Ball", position=(540, 760), initial_velocity=(350, -80), radius=50, color=PALETTE[1]))
    return project


def escape_and_respawn() -> BounceBeatProject:
    """Rotating escape ring surrounded by four walls.

    Escaping balls create a replacement at the ring center when they hit any wall.
    The escaped source is removed, preventing repeated outside-wall duplication.
    """
    project = _base("Escape and Respawn")
    project.scene.physics.gravity = (0.0, 360.0)
    project.scene.physics.substeps = 2
    project.scene.physics.max_collision_substeps = 24
    project.scene.physics.collision_iterations = 20
    _arena(project, 70)
    ring = RingObject(
        name="Rotating Escape Ring", position=(540, 960), radius=430, thickness=24,
        opening_angle=48, rotation_speed=32, segments=180, color=PALETTE[4], glow=0.7,
    )
    ball = BallObject(
        name="Respawning Escape Ball", position=(540, 760), initial_velocity=(350, -80),
        radius=50, color=PALETTE[1], duplication_trigger=DuplicationTrigger.ANY_WALL,
        duplication_mode=DuplicationMode.EXACT, max_duplicates=1, max_generation=100,
        duplication_spawn_mode=DuplicationSpawnMode.SELECTED_OBJECT_CENTER,
        duplication_spawn_target_id=ring.id, duplication_spawn_spread=260.0,
        duplication_velocity_mode=DuplicationVelocityMode.INITIAL, duplication_spawn_count=3,
        remove_source_after_duplication=True, reset_generation_on_respawn=True,
    )
    project.scene.extend([ring, ball])
    return project

def duplicate_on_bounce() -> BounceBeatProject:
    project = _base("Duplicate on Bounce")
    _arena(project, 75)
    project.scene.physics.max_balls = 140
    project.scene.add(BallObject(
        name="Duplicator", position=(540, 400), initial_velocity=(310, 80), radius=46,
        duplication_trigger=DuplicationTrigger.COLLISION_COUNT,
        duplication_every_collisions=3,
        duplication_mode=DuplicationMode.VELOCITY_VARIATION,
        max_duplicates=8,
        max_generation=4,
        color_mode=ColorMode.NEXT_PALETTE,
        color=PALETTE[0],
    ))
    return project


def multi_instrument_orchestra() -> BounceBeatProject:
    project = _base("Multi-Instrument Orchestra")
    project.midi_playback.mapping_mode = MidiMappingMode.PER_BALL
    project.scene.physics.gravity = (0.0, 520.0)
    _arena(project)
    for index, (x, y, velocity, label) in enumerate([
        (280, 480, (330, 40), "Piano Ball"),
        (800, 520, (-310, 10), "Bass Ball"),
        (340, 1050, (280, -280), "Drum Ball"),
        (750, 1150, (-250, -310), "Melody Ball"),
    ]):
        project.scene.add(BallObject(
            name=label, position=(x, y), initial_velocity=velocity, radius=48 + index * 4,
            color=PALETTE[index], midi_track_ids=[f"AUTO:{index}"], color_mode=ColorMode.CYCLE,
        ))
    return project


def expanding_rings() -> BounceBeatProject:
    project = _base("Expanding Rings")
    project.scene.physics.gravity = (0.0, 0.0)
    center = (540, 960)
    for index, radius in enumerate((170, 290, 410, 530)):
        project.scene.add(RingObject(
            name=f"Ring {index + 1}", position=center, radius=radius, thickness=20, segments=160,
            opening_angle=38, opening_rotation=index * 72, rotation_speed=(-1 if index % 2 else 1) * (18 + index * 7),
            expand_rate=(8 if index % 2 else -6), minimum_radius=120, maximum_radius=620,
            color=PALETTE[index], midi_track_ids=[f"AUTO:{index}"], glow=0.5,
        ))
    project.scene.add(BallObject(name="Center Ball", position=center, initial_velocity=(410, 130), radius=44, color=PALETTE[4]))
    return project


def color_explosion() -> BounceBeatProject:
    project = _base("Color Explosion")
    _arena(project)
    project.scene.add(BallObject(
        name="Color Ball", position=(540, 430), initial_velocity=(480, 10), radius=56,
        color_mode=ColorMode.RANDOM_BRIGHT, particle_count=46, glow=0.9,
        trail_length=75, trail_thickness=12,
    ))
    return project


def obstacle_course() -> BounceBeatProject:
    project = _base("Obstacle Course")
    project.scene.physics.gravity = (0.0, 480.0)
    project.scene.physics.substeps = 2
    project.scene.physics.max_collision_substeps = 20
    _arena(project, 55)
    for index, position in enumerate(((250, 520), (830, 670), (400, 1030), (720, 1300))):
        project.scene.add(BumperObject(name=f"Bumper {index+1}", position=position, radius=68, color=PALETTE[index], glow=0.6))
    project.scene.add(PolygonObject(name="Rotating Bar 1", position=(540, 790), rotation_speed=48, color=PALETTE[4]))
    project.scene.add(PolygonObject(name="Rotating Bar 2", position=(540, 1450), rotation_speed=-36, color=PALETTE[2]))
    portal_a = PortalObject(name="Portal A", position=(180, 1580), radius=62, color=PALETTE[0])
    portal_b = PortalObject(name="Portal B", position=(900, 310), radius=62, color=PALETTE[3])
    portal_a.target_portal_id = portal_b.id
    portal_b.target_portal_id = portal_a.id
    project.scene.extend([portal_a, portal_b])
    project.scene.add(BallObject(name="Course Ball", position=(540, 180), initial_velocity=(220, 50), radius=50, color=PALETTE[1]))
    return project


def music_visualizer() -> BounceBeatProject:
    project = _base("Music Visualizer")
    project.midi_playback.mapping_mode = MidiMappingMode.TIMELINE_SYNCHRONIZED
    project.scene.physics.gravity = (0.0, 0.0)
    for index in range(8):
        angle = index / 8 * 6.283185307
        x = 540 + 300 * __import__("math").cos(angle)
        y = 960 + 300 * __import__("math").sin(angle)
        project.scene.add(BallObject(
            name=f"Track Visual {index+1}", position=(x, y), initial_velocity=(0, 0), gravity_scale=0,
            radius=58, color=PALETTE[index % len(PALETTE)], midi_track_ids=[f"AUTO:{index}"],
            trail_enabled=False, particles_enabled=True, collision_cooldown_ms=0,
        ))
    project.scene.add(TextOverlayObject(name="Visualizer Title", position=(540, 180), text="MUSIC VISUALIZER", font_size=68, color="#F8FAFC"))
    return project


_FACTORIES = {
    "Classic Bounce": classic_bounce,
    "Circular Escape": circular_escape,
    "Escape and Respawn": escape_and_respawn,
    "Duplicate on Bounce": duplicate_on_bounce,
    "Multi-Instrument Orchestra": multi_instrument_orchestra,
    "Expanding Rings": expanding_rings,
    "Color Explosion": color_explosion,
    "Obstacle Course": obstacle_course,
    "Music Visualizer": music_visualizer,
}


def create_preset(name: str) -> BounceBeatProject:
    try:
        return _FACTORIES[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown preset: {name}") from exc


def assign_auto_tracks(project: BounceBeatProject) -> None:
    selected = project.selected_track_ids
    if not selected:
        return
    for obj in project.scene.objects:
        assigned: list[str] = []
        for track_id in obj.midi_track_ids:
            if track_id.startswith("AUTO:"):
                try:
                    index = int(track_id.split(":", 1)[1])
                except ValueError:
                    index = 0
                assigned.append(selected[index % len(selected)])
            else:
                assigned.append(track_id)
        obj.midi_track_ids = assigned


def export_builtin_presets(destination: str | Path | None = None) -> list[Path]:
    output = Path(destination) if destination else resource_path("assets", "presets")
    output.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name in PRESET_NAMES:
        project = create_preset(name)
        path = output / f"{name.lower().replace(' ', '_').replace('-', '_')}.json"
        path.write_text(json.dumps(project.to_dict(), indent=2), encoding="utf-8")
        paths.append(path)
    return paths
