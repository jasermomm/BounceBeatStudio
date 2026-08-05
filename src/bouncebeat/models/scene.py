from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, Iterable, TypeAlias

from .enums import (
    BallAppearance,
    CameraMode,
    ColorMode,
    DuplicationMode,
    DuplicationSpawnMode,
    DuplicationTrigger,
    DuplicationVelocityMode,
    ExportMode,
    MidiMappingMode,
    ObjectKind,
    Waveform,
)

Vec2: TypeAlias = tuple[float, float]
Color: TypeAlias = str


def new_id(prefix: str = "obj") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass(slots=True)
class PhysicsSettings:
    gravity: Vec2 = (0.0, 900.0)
    air_resistance: float = 0.995
    simulation_speed: float = 1.0
    physics_hz: int = 120
    substeps: int = 1
    continuous_collision_detection: bool = True
    max_collision_substeps: int = 16
    collision_skin: float = 1.5
    collision_iterations: int = 16
    global_friction: float = 0.5
    global_restitution: float = 0.92
    maximum_speed: float = 2500.0
    world_boundaries: bool = True
    wraparound: bool = False
    deterministic_seed: int = 1337
    max_balls: int = 500
    max_particles: int = 8000

    @property
    def fixed_timestep(self) -> float:
        return 1.0 / max(1, self.physics_hz)


@dataclass(slots=True)
class RenderSettings:
    width: int = 1080
    height: int = 1920
    fps: int = 60
    preview_scale: float = 0.5
    background_color: Color = "#0B1020"
    transparent: bool = False
    show_fps: bool = True
    show_grid: bool = False
    show_safe_area: bool = False
    preview_quality: str = "high"


@dataclass(slots=True)
class CameraSettings:
    mode: CameraMode = CameraMode.STATIC
    pan: Vec2 = (0.0, 0.0)
    zoom: float = 1.0
    smoothing: float = 0.12
    follow_object_id: str | None = None
    shake_intensity: float = 0.0
    framing: str = "portrait"


@dataclass(slots=True)
class RecordingSettings:
    mode: ExportMode = ExportMode.OFFLINE
    duration_seconds: float = 30.0
    container: str = "mp4"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 18
    bitrate: str = ""
    audio_bitrate: str = "192k"
    output_path: str = ""
    hardware_encoder: str = "auto"
    include_audio: bool = True
    image_sequence: bool = False
    audio_only: bool = False
    video_only: bool = False
    preserve_partial: bool = True


@dataclass(slots=True)
class MidiPlaybackSettings:
    mapping_mode: MidiMappingMode = MidiMappingMode.SEQUENTIAL
    tempo_multiplier: float = 1.0
    transpose: int = 0
    octave_shift: int = 0
    velocity_multiplier: float = 1.0
    minimum_velocity: int = 1
    maximum_velocity: int = 127
    note_duration_ms: int = 180
    sustain: bool = False
    loop: bool = True
    restart_on_simulation_restart: bool = True
    continue_position: bool = False
    reverse_order: bool = False
    shuffle_order: bool = False
    quantization: str = "off"
    scale_filter: str = "chromatic"
    instrument_override: int | None = None
    channel_override: int | None = None
    polyphony_limit: int = 64
    chord_window_ms: int = 35
    collision_cooldown_ms: int = 80
    strength_controls_velocity: bool = True
    strength_controls_volume: bool = False
    strength_controls_duration: bool = False
    strength_controls_pitch: bool = False
    strength_controls_particles: bool = True
    strength_controls_glow: bool = True
    strength_controls_size: bool = False
    strength_controls_camera_shake: bool = False


@dataclass(slots=True)
class AudioSettings:
    backend: str = "auto"
    soundfont_path: str = ""
    audio_device: str = "default"
    master_volume: float = 0.8
    sample_rate: int = 48000
    buffer_size: int = 512
    latency_ms: int = 30
    fallback_waveform: Waveform = Waveform.SINE


@dataclass(slots=True)
class PaletteSettings:
    colors: list[Color] = field(
        default_factory=lambda: ["#FF4D6D", "#FFD166", "#06D6A0", "#118AB2", "#8338EC"]
    )
    mode: ColorMode = ColorMode.CYCLE
    random_seed: int = 1337
    background: Color = "#0B1020"
    trail: Color = "#FFFFFF"
    obstacle: Color = "#CAD5E2"
    ring: Color = "#9CA3FF"
    particle: Color = "#FFFFFF"
    glow: Color = "#FFFFFF"
    text: Color = "#F8FAFC"
    guide: Color = "#64748B"
    fade_seconds: float = 0.18


@dataclass(slots=True)
class TimelineSettings:
    start_seconds: float = 0.0
    end_seconds: float = 30.0
    loop_start_seconds: float = 0.0
    loop_end_seconds: float = 0.0
    zoom: float = 1.0
    scroll_seconds: float = 0.0


@dataclass(slots=True)
class BaseObject:
    id: str = field(default_factory=new_id)
    name: str = "Object"
    kind: ObjectKind = ObjectKind.BALL
    visible: bool = True
    locked: bool = False
    group: str = ""
    position: Vec2 = (540.0, 960.0)
    rotation: float = 0.0
    color: Color = "#FFFFFF"
    glow: float = 0.0
    midi_track_ids: list[str] = field(default_factory=list)
    midi_channel: int | None = None
    midi_trigger: bool = True
    z_index: int = 0


@dataclass(slots=True)
class BallObject(BaseObject):
    kind: ObjectKind = field(default=ObjectKind.BALL, init=False)
    name: str = "Ball"
    radius: float = 48.0
    mass: float = 1.0
    initial_velocity: Vec2 = (320.0, -180.0)
    maximum_speed: float = 1800.0
    gravity_scale: float = 1.0
    restitution: float = 0.94
    friction: float = 0.25
    angular_velocity: float = 0.0
    appearance: BallAppearance = BallAppearance.GLOSSY
    reflections_enabled: bool = True
    reflection_strength: float = 0.85
    reflection_size: float = 0.42
    reflection_offset: Vec2 = (-0.30, -0.34)
    shading_strength: float = 0.30
    outline_enabled: bool = True
    outline_color: Color = "#FFFFFF"
    outline_opacity: float = 0.35
    outline_width: float = 2.4
    color_mode: ColorMode = ColorMode.CYCLE
    change_color_on_collision: bool = True
    change_color_on_note: bool = True
    trail_enabled: bool = True
    trail_length: int = 45
    trail_thickness: float = 12.0
    trail_opacity: float = 0.65
    duplication_trigger: DuplicationTrigger = DuplicationTrigger.NONE
    duplication_mode: DuplicationMode = DuplicationMode.VELOCITY_VARIATION
    duplication_every_collisions: int = 1
    duplication_strength_threshold: float = 250.0
    duplication_target_id: str | None = None
    duplication_midi_note: int = 60
    duplication_interval_seconds: float = 1.0
    duplication_beat_interval: float = 1.0
    duplication_spawn_mode: DuplicationSpawnMode = DuplicationSpawnMode.COLLISION_POSITION
    duplication_spawn_target_id: str | None = None
    duplication_spawn_position: Vec2 = (540.0, 960.0)
    duplication_spawn_spread: float = 0.0
    duplication_velocity_mode: DuplicationVelocityMode = DuplicationVelocityMode.CURRENT
    duplication_spawn_count: int = 1
    remove_source_after_duplication: bool = False
    reset_generation_on_respawn: bool = True
    duplicate_velocity_variation: float = 0.25
    duplicate_size_variation: float = 0.12
    max_duplicates: int = 12
    generation: int = 0
    max_generation: int = 5
    particles_enabled: bool = True
    particle_count: int = 18
    lifetime_seconds: float = 0.0
    collision_cooldown_ms: int = 80


@dataclass(slots=True)
class WallObject(BaseObject):
    kind: ObjectKind = field(default=ObjectKind.WALL, init=False)
    name: str = "Wall"
    start: Vec2 = (120.0, 200.0)
    end: Vec2 = (960.0, 200.0)
    thickness: float = 16.0
    restitution: float = 0.95
    friction: float = 0.4
    break_on_hit: bool = False
    break_strength: float = 1100.0


@dataclass(slots=True)
class RingObject(BaseObject):
    kind: ObjectKind = field(default=ObjectKind.RING, init=False)
    name: str = "Ring"
    radius: float = 360.0
    thickness: float = 18.0
    rotation_speed: float = 0.0
    opening_angle: float = 0.0
    opening_rotation: float = 0.0
    expand_rate: float = 0.0
    minimum_radius: float = 20.0
    maximum_radius: float = 1200.0
    collision_mode: str = "solid"
    break_on_hit: bool = False
    break_strength: float = 1000.0
    segments: int = 96


@dataclass(slots=True)
class BumperObject(BaseObject):
    kind: ObjectKind = field(default=ObjectKind.BUMPER, init=False)
    name: str = "Bumper"
    radius: float = 64.0
    restitution: float = 1.15
    impulse: float = 250.0


@dataclass(slots=True)
class PolygonObject(BaseObject):
    kind: ObjectKind = field(default=ObjectKind.POLYGON, init=False)
    name: str = "Obstacle"
    vertices: list[Vec2] = field(
        default_factory=lambda: [(-120.0, -14.0), (120.0, -14.0), (120.0, 14.0), (-120.0, 14.0)]
    )
    rotation_speed: float = 0.0
    restitution: float = 0.95
    friction: float = 0.4
    break_on_hit: bool = False
    break_strength: float = 950.0


@dataclass(slots=True)
class PortalObject(BaseObject):
    kind: ObjectKind = field(default=ObjectKind.PORTAL, init=False)
    name: str = "Portal"
    radius: float = 58.0
    target_portal_id: str | None = None
    preserve_velocity: bool = True
    exit_speed_multiplier: float = 1.0
    cooldown_ms: int = 350


@dataclass(slots=True)
class EmitterObject(BaseObject):
    kind: ObjectKind = field(default=ObjectKind.EMITTER, init=False)
    name: str = "Emitter"
    spawn_area: Vec2 = (0.0, 0.0)
    spawn_interval: float = 1.0
    initial_ball_count: int = 0
    maximum_ball_count: int = 100
    radius_range: Vec2 = (28.0, 52.0)
    speed_range: Vec2 = (120.0, 480.0)
    direction_range: Vec2 = (0.0, 360.0)
    lifetime_range: Vec2 = (0.0, 0.0)
    enabled: bool = True
    random_seed: int = 1337


@dataclass(slots=True)
class TextOverlayObject(BaseObject):
    kind: ObjectKind = field(default=ObjectKind.TEXT, init=False)
    name: str = "Text"
    text: str = "BounceBeat Studio"
    font_size: float = 42.0
    opacity: float = 1.0
    alignment: str = "center"


@dataclass(slots=True)
class ParticleSystemObject(BaseObject):
    kind: ObjectKind = field(default=ObjectKind.PARTICLE_SYSTEM, init=False)
    name: str = "Particles"
    enabled: bool = True
    maximum_particles: int = 2500
    style: str = "sparks"
    gravity: Vec2 = (0.0, 240.0)
    drag: float = 0.98


SceneObject: TypeAlias = (
    BallObject
    | WallObject
    | RingObject
    | BumperObject
    | PolygonObject
    | PortalObject
    | EmitterObject
    | TextOverlayObject
    | ParticleSystemObject
)

_OBJECT_TYPES: dict[str, type[SceneObject]] = {
    ObjectKind.BALL.value: BallObject,
    ObjectKind.WALL.value: WallObject,
    ObjectKind.RING.value: RingObject,
    ObjectKind.BUMPER.value: BumperObject,
    ObjectKind.POLYGON.value: PolygonObject,
    ObjectKind.PORTAL.value: PortalObject,
    ObjectKind.EMITTER.value: EmitterObject,
    ObjectKind.TEXT.value: TextOverlayObject,
    ObjectKind.PARTICLE_SYSTEM.value: ParticleSystemObject,
}


@dataclass(slots=True)
class Scene:
    logical_width: float = 1080.0
    logical_height: float = 1920.0
    objects: list[SceneObject] = field(default_factory=list)
    physics: PhysicsSettings = field(default_factory=PhysicsSettings)
    palette: PaletteSettings = field(default_factory=PaletteSettings)

    def add(self, obj: SceneObject) -> SceneObject:
        self.objects.append(obj)
        self._normalize_z_indexes()
        return obj

    def extend(self, objects: Iterable[SceneObject]) -> None:
        self.objects.extend(objects)
        self._normalize_z_indexes()

    def get(self, object_id: str | None) -> SceneObject | None:
        if not object_id:
            return None
        return next((obj for obj in self.objects if obj.id == object_id), None)

    def remove(self, object_id: str) -> SceneObject | None:
        for index, obj in enumerate(self.objects):
            if obj.id == object_id:
                removed = self.objects.pop(index)
                self._normalize_z_indexes()
                return removed
        return None

    def duplicate(self, object_id: str) -> SceneObject | None:
        original = self.get(object_id)
        if original is None:
            return None
        clone = copy.deepcopy(original)
        clone.id = new_id(original.kind.value)
        clone.name = f"{original.name} Copy"
        clone.position = (original.position[0] + 28.0, original.position[1] + 28.0)
        if isinstance(clone, BallObject):
            clone.generation = original.generation + 1
        self.add(clone)
        return clone

    def balls(self) -> list[BallObject]:
        return [obj for obj in self.objects if isinstance(obj, BallObject)]

    def _normalize_z_indexes(self) -> None:
        for index, obj in enumerate(self.objects):
            obj.z_index = index


def _enum_value(value: Any) -> Any:
    if hasattr(value, "value") and value.__class__.__module__ == "bouncebeat.models.enums":
        return value.value
    return value


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        result: dict[str, Any] = {}
        for f in fields(value):
            result[f.name] = dataclass_to_dict(getattr(value, f.name))
        return result
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, tuple):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(key): dataclass_to_dict(item) for key, item in value.items()}
    return _enum_value(value)


def _coerce_enum(field_name: str, value: Any) -> Any:
    vector_fields = {
        "position", "gravity", "pan", "initial_velocity", "start", "end",
        "spawn_area", "radius_range", "speed_range", "direction_range",
        "lifetime_range", "duplication_spawn_position", "reflection_offset",
    }
    if field_name in vector_fields and isinstance(value, list):
        value = tuple(value)
    elif field_name == "vertices" and isinstance(value, list):
        value = [tuple(item) if isinstance(item, list) else item for item in value]
    enum_fields = {
        "kind": ObjectKind,
        "appearance": BallAppearance,
        "mode": ColorMode,
        "color_mode": ColorMode,
        "mapping_mode": MidiMappingMode,
        "duplication_trigger": DuplicationTrigger,
        "duplication_mode": DuplicationMode,
        "duplication_spawn_mode": DuplicationSpawnMode,
        "duplication_velocity_mode": DuplicationVelocityMode,
        "waveform": Waveform,
        "fallback_waveform": Waveform,
    }
    if field_name == "mode" and value in {m.value for m in CameraMode}:
        return CameraMode(value)
    if field_name == "mode" and value in {m.value for m in ExportMode}:
        return ExportMode(value)
    enum_type = enum_fields.get(field_name)
    if enum_type and isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError:
            return value
    return value


def object_from_dict(data: dict[str, Any]) -> SceneObject:
    kind = str(data.get("kind", ObjectKind.BALL.value))
    cls = _OBJECT_TYPES.get(kind, BallObject)
    accepted = {f.name for f in fields(cls) if f.init}
    kwargs = {
        key: _coerce_enum(key, value)
        for key, value in data.items()
        if key in accepted
    }
    return cls(**kwargs)


def dataclass_from_dict(cls: type[Any], data: dict[str, Any]) -> Any:
    accepted = {f.name for f in fields(cls) if f.init}
    kwargs = {
        key: _coerce_enum(key, value)
        for key, value in data.items()
        if key in accepted
    }
    return cls(**kwargs)


def scene_to_dict(scene: Scene) -> dict[str, Any]:
    return dataclass_to_dict(scene)


def scene_from_dict(data: dict[str, Any]) -> Scene:
    scene = Scene(
        logical_width=float(data.get("logical_width", 1080.0)),
        logical_height=float(data.get("logical_height", 1920.0)),
        physics=dataclass_from_dict(PhysicsSettings, data.get("physics", {})),
        palette=dataclass_from_dict(PaletteSettings, data.get("palette", {})),
    )
    scene.objects = [object_from_dict(item) for item in data.get("objects", [])]
    scene._normalize_z_indexes()
    return scene
