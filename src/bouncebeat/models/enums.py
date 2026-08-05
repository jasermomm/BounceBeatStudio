from __future__ import annotations

from enum import StrEnum


class ObjectKind(StrEnum):
    BALL = "ball"
    WALL = "wall"
    RING = "ring"
    POLYGON = "polygon"
    BUMPER = "bumper"
    PORTAL = "portal"
    EMITTER = "emitter"
    TEXT = "text"
    PARTICLE_SYSTEM = "particle_system"


class MidiMappingMode(StrEnum):
    SEQUENTIAL = "sequential"
    LAYERED = "layered"
    ROUND_ROBIN = "round_robin"
    RANDOM_TRACK = "random_track"
    PER_BALL = "per_ball"
    PER_SURFACE = "per_surface"
    TIMELINE_SYNCHRONIZED = "timeline_synchronized"
    COLLISION_CONTROLLED_TIMELINE = "collision_controlled_timeline"


class ColorMode(StrEnum):
    SINGLE = "single"
    RANDOM_PALETTE = "random_palette"
    CYCLE = "cycle"
    TIME_GRADIENT = "time_gradient"
    SPEED_GRADIENT = "speed_gradient"
    PITCH_GRADIENT = "pitch_gradient"
    TRACK = "track"
    INSTRUMENT = "instrument"
    COLLISION_STRENGTH = "collision_strength"
    RANDOM_RGB = "random_rgb"
    RANDOM_BRIGHT = "random_bright"
    RANDOM_PASTEL = "random_pastel"
    RAINBOW = "rainbow"
    INHERIT = "inherit"
    NEXT_PALETTE = "next_palette"


class BallAppearance(StrEnum):
    FLAT = "flat"
    SOFT_SHADED = "soft_shaded"
    GLOSSY = "glossy"
    NEON = "neon"


class DuplicationTrigger(StrEnum):
    NONE = "none"
    EVERY_COLLISION = "every_collision"
    SELECTED_OBJECT = "selected_object"
    STRENGTH_THRESHOLD = "strength_threshold"
    COLLISION_COUNT = "collision_count"
    MIDI_NOTE = "midi_note"
    BEAT = "beat"
    ENTER_REGION = "enter_region"
    LEAVE_RING = "leave_ring"
    INTERVAL = "interval"
    ANY_WALL = "any_wall"


class DuplicationMode(StrEnum):
    EXACT = "exact"
    VELOCITY_VARIATION = "velocity_variation"
    SIZE_VARIATION = "size_variation"
    PALETTE_PROGRESSION = "palette_progression"
    DIFFERENT_TRACK = "different_track"
    NEXT_CHANNEL = "next_channel"


class DuplicationSpawnMode(StrEnum):
    COLLISION_POSITION = "collision_position"
    ORIGINAL_POSITION = "original_position"
    SELECTED_OBJECT_CENTER = "selected_object_center"
    CUSTOM_POSITION = "custom_position"


class DuplicationVelocityMode(StrEnum):
    CURRENT = "current"
    INITIAL = "initial"
    RANDOM_DIRECTION = "random_direction"


class CameraMode(StrEnum):
    STATIC = "static"
    FOLLOW_SELECTED = "follow_selected"
    FOLLOW_AVERAGE = "follow_average"
    AUTO_ZOOM = "auto_zoom"


class ExportMode(StrEnum):
    REALTIME = "realtime"
    OFFLINE = "offline"


class Waveform(StrEnum):
    SINE = "sine"
    SQUARE = "square"
    TRIANGLE = "triangle"
    SAWTOOTH = "sawtooth"
