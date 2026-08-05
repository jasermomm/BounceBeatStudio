from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class NoteEvent:
    time: float
    pitch: int
    velocity: int
    duration: float
    track_id: str
    channel: int
    program: int
    pan: float = 0.0
    volume: float = 1.0
    source_object_id: str = ""


@dataclass(slots=True, frozen=True)
class PhysicsEvent:
    time: float
    event_type: str
    object_a: str
    object_b: str = ""
    position: tuple[float, float] = (0.0, 0.0)
    strength: float = 0.0
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class Particle:
    position: tuple[float, float]
    velocity: tuple[float, float]
    color: str
    radius: float
    lifetime: float
    age: float = 0.0


@dataclass(slots=True)
class Ripple:
    position: tuple[float, float]
    color: str
    radius: float
    speed: float
    lifetime: float
    age: float = 0.0


@dataclass(slots=True)
class RuntimeObjectState:
    id: str
    position: tuple[float, float]
    rotation: float
    velocity: tuple[float, float] = (0.0, 0.0)
    radius: float = 0.0
    color: str = "#FFFFFF"
    pulse: float = 0.0
    size_pulse: float = 0.0
    glow_pulse: float = 0.0
    visible: bool = True
    trail: list[tuple[float, float]] = field(default_factory=list)


@dataclass(slots=True)
class SimulationSnapshot:
    time: float
    frame: int
    collision_count: int
    active_ball_count: int
    object_states: dict[str, RuntimeObjectState]
    particles: list[Particle]
    ripples: list[Ripple]
    current_notes: list[int] = field(default_factory=list)
    dropped_frames: int = 0
    physics_hz: int = 120
    camera_shake: float = 0.0
