from __future__ import annotations

import copy
import logging
import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from typing import Callable

from bouncebeat.midi.sequencer import NoteSequencer
from bouncebeat.models.enums import (
    ColorMode, DuplicationMode, DuplicationSpawnMode, DuplicationTrigger,
    DuplicationVelocityMode, MidiMappingMode, ObjectKind,
)
from bouncebeat.models.events import (
    NoteEvent,
    Particle,
    PhysicsEvent,
    Ripple,
    RuntimeObjectState,
    SimulationSnapshot,
)
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.simulation.geometry import (
    add,
    angular_velocity_at,
    closest_point_on_segment,
    dot,
    length,
    minimum_polygon_half_width,
    multiply,
    normalized,
    point_in_polygon,
    polygon_world_vertices,
    ring_arc_segments,
    subtract,
    transform_point,
)
from bouncebeat.models.scene import (
    BallObject,
    BaseObject,
    BumperObject,
    EmitterObject,
    PolygonObject,
    PortalObject,
    RingObject,
    SceneObject,
    WallObject,
    new_id,
)
from bouncebeat.utilities.colors import interpolate_color, random_color, rainbow_color

try:
    import pymunk
except ImportError:
    pymunk = None

logger = logging.getLogger("bouncebeat.simulation")


class SimulationUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class _EmitterRuntime:
    elapsed: float = 0.0
    spawned: int = 0
    initialized: bool = False


class SimulationEngine:
    """Deterministic fixed-step simulation facade.

    Pymunk is used when available. A compact deterministic fallback keeps the editor,
    tests, and first-launch experience functional if the optional binary wheel cannot
    be imported; installing the declared requirements automatically selects Pymunk.
    """

    def __init__(
        self,
        project: BounceBeatProject,
        note_callback: Callable[[list[NoteEvent]], None] | None = None,
        event_callback: Callable[[PhysicsEvent], None] | None = None,
        force_fallback: bool = False,
    ) -> None:
        backend_type = _FallbackBackend if force_fallback or pymunk is None else _PymunkBackend
        self._backend = backend_type(project, note_callback, event_callback)

    @property
    def project(self) -> BounceBeatProject:
        return self._backend.project

    @property
    def playing(self) -> bool:
        return self._backend.playing

    @playing.setter
    def playing(self, value: bool) -> None:
        self._backend.playing = value

    @property
    def time(self) -> float:
        return self._backend.time

    @property
    def fixed_dt(self) -> float:
        return self._backend.fixed_dt

    @property
    def physics_events(self) -> list[PhysicsEvent]:
        return self._backend.physics_events

    @property
    def note_events(self) -> list[NoteEvent]:
        return self._backend.note_events

    @property
    def using_pymunk(self) -> bool:
        return isinstance(self._backend, _PymunkBackend)

    @property
    def models(self) -> dict[str, SceneObject]:
        return self._backend.models

    def reset(self) -> None:
        self._backend.reset()

    def step(self, dt: float | None = None) -> SimulationSnapshot:
        return self._backend.step(dt)

    def snapshot(self) -> SimulationSnapshot:
        return self._backend.snapshot()

    def set_object_position(self, object_id: str, position: tuple[float, float]) -> None:
        self._backend.set_object_position(object_id, position)

    def set_selected_object(self, object_id: str | None) -> None:
        self._backend.selected_object_id = object_id


class _BackendBase:
    def __init__(
        self,
        project: BounceBeatProject,
        note_callback: Callable[[list[NoteEvent]], None] | None,
        event_callback: Callable[[PhysicsEvent], None] | None,
    ) -> None:
        self.project = project
        self.note_callback = note_callback
        self.event_callback = event_callback
        self.fixed_dt = project.scene.physics.fixed_timestep
        self.playing = False
        self.selected_object_id: str | None = None
        self.time = 0.0
        self.frame = 0
        self.collision_count = 0
        self.dropped_frames = 0
        self.camera_shake = 0.0
        self.models: dict[str, SceneObject] = {}
        self.states: dict[str, RuntimeObjectState] = {}
        self.trails: dict[str, deque[tuple[float, float]]] = {}
        self.particles: list[Particle] = []
        self.ripples: list[Ripple] = []
        self.physics_events: list[PhysicsEvent] = []
        self.note_events: list[NoteEvent] = []
        self.active_notes: list[tuple[float, int]] = []
        self._collision_last_time: dict[tuple[str, str], float] = {}
        self._duplicate_counts: dict[str, int] = defaultdict(int)
        self._portal_last_time: dict[str, float] = {}
        self._collision_counts_by_ball: dict[str, int] = defaultdict(int)
        self._palette_indices: dict[str, int] = defaultdict(int)
        self._emitter_runtime: dict[str, _EmitterRuntime] = defaultdict(_EmitterRuntime)
        self._spawn_times: dict[str, float] = {}
        self._inside_regions: dict[tuple[str, str], bool] = {}
        self._pending_removals: set[str] = set()
        self._pending_duplicate_ids: set[str] = set()
        self.rng = random.Random(project.scene.physics.deterministic_seed)
        self.sequencer = NoteSequencer(
            project.midi_asset,
            project.selected_track_ids,
            project.midi_playback,
            project.scene.physics.deterministic_seed,
        )

    def reset(self) -> None:
        preserve_sequencer = None
        playback = self.project.midi_playback
        if hasattr(self, "sequencer") and (
            playback.continue_position or not playback.restart_on_simulation_restart
        ):
            preserve_sequencer = {
                "indices": dict(self.sequencer.indices),
                "round_robin_index": self.sequencer.round_robin_index,
                "timeline_cursor": self.sequencer.timeline_cursor,
                "rng_state": self.sequencer.rng.getstate(),
            }

        self.time = 0.0
        self.frame = 0
        self.collision_count = 0
        self.dropped_frames = 0
        self.camera_shake = 0.0
        self.models = {obj.id: copy.deepcopy(obj) for obj in self.project.scene.objects}
        self.states.clear()
        self.trails.clear()
        self.particles.clear()
        self.ripples.clear()
        self.physics_events.clear()
        self.note_events.clear()
        self.active_notes.clear()
        self._collision_last_time.clear()
        self._duplicate_counts.clear()
        self._portal_last_time.clear()
        self._collision_counts_by_ball.clear()
        self._palette_indices.clear()
        self._emitter_runtime.clear()
        self._spawn_times.clear()
        self._inside_regions.clear()
        self._pending_removals.clear()
        self._pending_duplicate_ids.clear()
        self.rng = random.Random(self.project.scene.physics.deterministic_seed)
        self.sequencer = NoteSequencer(
            self.project.midi_asset,
            self.project.selected_track_ids,
            self.project.midi_playback,
            self.project.scene.physics.deterministic_seed,
        )
        if preserve_sequencer is not None:
            self.sequencer.indices.update(preserve_sequencer["indices"])
            self.sequencer.round_robin_index = preserve_sequencer["round_robin_index"]
            self.sequencer.timeline_cursor = preserve_sequencer["timeline_cursor"]
            self.sequencer.rng.setstate(preserve_sequencer["rng_state"])

    def _color_for(
        self,
        model: BaseObject,
        speed: float = 0.0,
        pitch: int | None = None,
        strength: float = 0.0,
        track_id: str = "",
        program: int | None = None,
    ) -> str:
        colors = self.project.scene.palette.colors or [model.color]
        mode = getattr(model, "color_mode", self.project.scene.palette.mode)
        index = self._palette_indices[model.id]
        if mode in {ColorMode.CYCLE, ColorMode.NEXT_PALETTE}:
            color = colors[index % len(colors)]
            self._palette_indices[model.id] = index + 1
            return color
        if mode == ColorMode.RANDOM_PALETTE:
            return self.rng.choice(colors)
        if mode == ColorMode.RANDOM_RGB:
            return random_color("rgb", self.rng)
        if mode == ColorMode.RANDOM_BRIGHT:
            return random_color("bright", self.rng)
        if mode == ColorMode.RANDOM_PASTEL:
            return random_color("pastel", self.rng)
        if mode == ColorMode.RAINBOW:
            return rainbow_color(self.time * 120.0 + index * 37.0)
        if mode == ColorMode.TIME_GRADIENT:
            transition = max(0.02, self.project.scene.palette.fade_seconds)
            position = (self.time / transition) % len(colors)
            left = int(math.floor(position))
            return interpolate_color(colors[left], colors[(left + 1) % len(colors)], position - left)
        if mode == ColorMode.SPEED_GRADIENT:
            return colors[min(len(colors) - 1, int(max(0.0, speed) / 400.0) % len(colors))]
        if mode == ColorMode.PITCH_GRADIENT and pitch is not None:
            return colors[pitch % len(colors)]
        if mode == ColorMode.TRACK:
            key = track_id or (model.midi_track_ids[0] if model.midi_track_ids else model.id)
            stable_index = sum((offset + 1) * byte for offset, byte in enumerate(key.encode("utf-8")))
            return colors[stable_index % len(colors)]
        if mode == ColorMode.INSTRUMENT:
            value = program if program is not None else (model.midi_channel or 0)
            return colors[value % len(colors)]
        if mode == ColorMode.COLLISION_STRENGTH:
            normalized = max(0.0, min(0.999999, strength / 1800.0))
            return colors[int(normalized * len(colors))]
        return model.color or colors[0]

    def _emit_notes(
        self,
        ball: BallObject,
        surface: BaseObject | None,
        strength: float,
    ) -> list[NoteEvent]:
        events = self.sequencer.trigger(
            time=self.time,
            strength=strength,
            source_object_id=ball.id,
            object_track_ids=ball.midi_track_ids,
            surface_track_ids=surface.midi_track_ids if surface else None,
        )
        if not events:
            return []
        channel_override = ball.midi_channel
        if (
            self.project.midi_playback.mapping_mode == MidiMappingMode.PER_SURFACE
            and surface is not None
            and surface.midi_channel is not None
        ):
            channel_override = surface.midi_channel
        if channel_override is not None:
            events = [replace(event, channel=int(channel_override) % 16) for event in events]
        self.note_events.extend(events)
        for event in events:
            self.active_notes.append((event.time + event.duration, event.pitch))
        state = self.states.get(ball.id)
        if state:
            state.pulse = 1.0
            state.size_pulse = max(state.size_pulse, 1.0)
            state.glow_pulse = max(state.glow_pulse, 1.0)
            if ball.change_color_on_note:
                first = events[0]
                state.color = self._color_for(
                    ball, math.hypot(*state.velocity), first.pitch, strength, first.track_id, first.program
                )
        if self.note_callback:
            self.note_callback(events)
        return events

    def _visual_collision(
        self,
        ball: BallObject,
        position: tuple[float, float],
        strength: float,
    ) -> None:
        state = self.states.get(ball.id)
        if state and ball.change_color_on_collision:
            state.color = self._color_for(ball, math.hypot(*state.velocity), strength=strength)
        color = state.color if state else ball.color
        intensity = max(0.25, min(2.5, strength / 500.0))
        glow_intensity = intensity if self.project.midi_playback.strength_controls_glow else 1.0
        size_intensity = intensity if self.project.midi_playback.strength_controls_size else 1.0
        if state:
            state.pulse = max(state.pulse, 1.0)
            state.glow_pulse = max(state.glow_pulse, glow_intensity)
            state.size_pulse = max(state.size_pulse, size_intensity)
        if self.project.midi_playback.strength_controls_camera_shake:
            self.camera_shake = max(self.camera_shake, min(1.0, strength / 1200.0))
        self.ripples.append(Ripple(position, color, ball.radius, max(80.0, strength * 0.25), 0.5))
        if ball.particles_enabled:
            particle_intensity = intensity if self.project.midi_playback.strength_controls_particles else 1.0
            count = min(ball.particle_count, max(2, int(ball.particle_count * particle_intensity)))
            for _ in range(count):
                angle = self.rng.random() * math.tau
                speed = self.rng.uniform(80.0, 260.0) * max(0.5, min(2.0, strength / 500.0))
                self.particles.append(
                    Particle(
                        position=position,
                        velocity=(math.cos(angle) * speed, math.sin(angle) * speed),
                        color=color,
                        radius=self.rng.uniform(2.0, 6.0),
                        lifetime=self.rng.uniform(0.25, 0.75),
                    )
                )
        maximum = self.project.scene.physics.max_particles
        if len(self.particles) > maximum:
            del self.particles[: len(self.particles) - maximum]

    def _update_effects(self, dt: float) -> None:
        gravity = self.project.scene.physics.gravity
        for particle in self.particles:
            particle.age += dt
            vx, vy = particle.velocity
            particle.velocity = (vx * 0.985, vy * 0.985 + gravity[1] * 0.12 * dt)
            particle.position = (
                particle.position[0] + particle.velocity[0] * dt,
                particle.position[1] + particle.velocity[1] * dt,
            )
        self.particles[:] = [particle for particle in self.particles if particle.age < particle.lifetime]
        for ripple in self.ripples:
            ripple.age += dt
            ripple.radius += ripple.speed * dt
        self.ripples[:] = [ripple for ripple in self.ripples if ripple.age < ripple.lifetime]
        for state in self.states.values():
            state.pulse = max(0.0, state.pulse - dt * 4.5)
            state.size_pulse = max(0.0, state.size_pulse - dt * 4.5)
            state.glow_pulse = max(0.0, state.glow_pulse - dt * 4.5)
        self.active_notes[:] = [item for item in self.active_notes if item[0] > self.time]
        self.camera_shake = max(0.0, self.camera_shake - dt * 3.5)

    def _timeline_notes(self, previous_time: float, current_time: float) -> None:
        events = self.sequencer.timeline_events_due(previous_time, current_time)
        if not events:
            return
        self.note_events.extend(events)
        selected_balls = [model for model in self.models.values() if isinstance(model, BallObject)]
        for event in events:
            self.active_notes.append((event.time + event.duration, event.pitch))
            target = next((ball for ball in selected_balls if event.track_id in ball.midi_track_ids), None)
            if target is None and selected_balls:
                target = selected_balls[event.pitch % len(selected_balls)]
            if target and target.id in self.states:
                state = self.states[target.id]
                state.pulse = 1.0
                state.size_pulse = max(state.size_pulse, 1.0)
                state.glow_pulse = max(state.glow_pulse, 1.0)
                state.color = self._color_for(
                    target, math.hypot(*state.velocity), event.pitch, event.velocity * 6.0, event.track_id, event.program
                )
                self._visual_collision(target, state.position, event.velocity * 6.0)
        if self.note_callback:
            self.note_callback(events)

    def _collision_allowed(self, a_id: str, b_id: str, cooldown_ms: int) -> bool:
        pair = tuple(sorted((a_id, b_id)))
        previous = self._collision_last_time.get(pair, -10_000.0)
        if self.time - previous < max(0, cooldown_ms) / 1000.0:
            return False
        self._collision_last_time[pair] = self.time
        return True

    def _register_collision(
        self,
        ball: BallObject,
        surface: BaseObject | None,
        position: tuple[float, float],
        strength: float,
    ) -> None:
        surface_id = surface.id if surface else "world"
        cooldown = max(ball.collision_cooldown_ms, self.project.midi_playback.collision_cooldown_ms)
        if not self._collision_allowed(ball.id, surface_id, cooldown):
            return
        self.collision_count += 1
        self._collision_counts_by_ball[ball.id] += 1
        event = PhysicsEvent(
            time=self.time,
            event_type="collision",
            object_a=ball.id,
            object_b=surface_id,
            position=position,
            strength=strength,
        )
        self.physics_events.append(event)
        if self.event_callback:
            self.event_callback(event)
        self._visual_collision(ball, position, strength)
        surface_allows_midi = surface is None or isinstance(surface, BallObject) or surface.midi_trigger
        note_events = self._emit_notes(ball, surface, strength) if ball.midi_trigger and surface_allows_midi else []
        self._maybe_duplicate(ball, surface, strength, note_events)

    def _register_ball_pair_collision(
        self,
        first: BallObject,
        second: BallObject,
        position: tuple[float, float],
        strength: float,
    ) -> None:
        cooldown = max(
            first.collision_cooldown_ms,
            second.collision_cooldown_ms,
            self.project.midi_playback.collision_cooldown_ms,
        )
        if not self._collision_allowed(first.id, second.id, cooldown):
            return
        self.collision_count += 1
        self._collision_counts_by_ball[first.id] += 1
        self._collision_counts_by_ball[second.id] += 1
        event = PhysicsEvent(
            time=self.time,
            event_type="collision",
            object_a=first.id,
            object_b=second.id,
            position=position,
            strength=strength,
        )
        self.physics_events.append(event)
        if self.event_callback:
            self.event_callback(event)
        for ball, surface in ((first, second), (second, first)):
            self._visual_collision(ball, position, strength)
            note_events = self._emit_notes(ball, surface, strength) if ball.midi_trigger else []
            self._maybe_duplicate(ball, surface, strength, note_events)

    @staticmethod
    def _requested_spawn_count(ball: BallObject) -> int:


        try:
            requested = int(ball.duplication_spawn_count)
        except (TypeError, ValueError):
            requested = 1
        return max(1, min(64, requested))

    def _available_duplicate_slots(self, ball: BallObject, reserved: int = 0) -> int:
        active_balls = sum(isinstance(model, BallObject) for model in self.models.values())
        effective_active = active_balls + max(0, reserved)
        if ball.remove_source_after_duplication:
            effective_active -= 1
        return max(0, self.project.scene.physics.max_balls - effective_active)

    def _pending_net_growth(self, ball: BallObject) -> int:
        requested = self._requested_spawn_count(ball)
        return max(0, requested - (1 if ball.remove_source_after_duplication else 0))

    def _can_duplicate(self, ball: BallObject, reserved: int = 0) -> bool:
        if self._available_duplicate_slots(ball, reserved) <= 0:
            return False
        if ball.generation >= ball.max_generation or self._duplicate_counts[ball.id] >= ball.max_duplicates:
            return False
        return True

    def _attempt_duplicate(self, ball: BallObject) -> bool:
        if not self._can_duplicate(ball):
            return False

        requested_count = self._requested_spawn_count(ball)
        create_count = min(requested_count, self._available_duplicate_slots(ball))
        if create_count <= 0:
            return False


        self._duplicate_counts[ball.id] += 1
        created_ids: list[str] = []
        for batch_index in range(create_count):
            previous_ids = set(self.models)
            self._spawn_duplicate(ball, batch_index=batch_index, batch_count=create_count)
            new_ids = sorted(set(self.models) - previous_ids)
            if not new_ids:
                continue
            created_id = new_ids[0]
            created_ids.append(created_id)
            event = PhysicsEvent(
                self.time, "ball_creation", created_id, ball.id,
                self.states.get(created_id, self.states[ball.id]).position, 0.0,
                {
                    "source": "duplication",
                    "generation": getattr(self.models.get(created_id), "generation", 0),
                    "batch_index": batch_index + 1,
                    "requested_count": requested_count,
                    "created_count": create_count,
                },
            )
            self.physics_events.append(event)
            if self.event_callback:
                self.event_callback(event)

        if created_ids and ball.remove_source_after_duplication:
            self._pending_removals.add(ball.id)
        return bool(created_ids)

    def _maybe_duplicate(
        self,
        ball: BallObject,
        surface: BaseObject | None,
        strength: float,
        note_events: list[NoteEvent] | None = None,
    ) -> None:
        trigger = ball.duplication_trigger
        should_duplicate = False
        if trigger == DuplicationTrigger.EVERY_COLLISION:
            should_duplicate = True
        elif trigger == DuplicationTrigger.SELECTED_OBJECT:
            should_duplicate = surface is not None and surface.id == ball.duplication_target_id
        elif trigger == DuplicationTrigger.STRENGTH_THRESHOLD:
            should_duplicate = strength >= ball.duplication_strength_threshold
        elif trigger == DuplicationTrigger.COLLISION_COUNT:
            every = max(1, ball.duplication_every_collisions)
            should_duplicate = self._collision_counts_by_ball[ball.id] % every == 0
        elif trigger == DuplicationTrigger.MIDI_NOTE:
            should_duplicate = any(event.pitch == ball.duplication_midi_note for event in (note_events or []))
        elif trigger == DuplicationTrigger.ANY_WALL:


            should_duplicate = surface is None or isinstance(surface, WallObject)
        if should_duplicate:
            self._attempt_duplicate(ball)

    @staticmethod
    def _region_radius(target: BaseObject) -> float:
        if hasattr(target, "radius"):
            return max(1.0, float(getattr(target, "radius")))
        if isinstance(target, PolygonObject) and target.vertices:
            return max(math.hypot(x, y) for x, y in target.vertices)
        return 60.0

    def _update_spatial_duplications(self) -> None:
        balls = [model for model in list(self.models.values()) if isinstance(model, BallObject)]
        for ball in balls:
            state = self.states.get(ball.id)
            if state is None or ball.duplication_trigger not in {DuplicationTrigger.ENTER_REGION, DuplicationTrigger.LEAVE_RING}:
                continue
            if ball.duplication_target_id:
                targets = [self.models.get(ball.duplication_target_id)]
            elif ball.duplication_trigger == DuplicationTrigger.LEAVE_RING:
                targets = [item for item in self.models.values() if isinstance(item, RingObject)]
            else:
                targets = []
            for target in [item for item in targets if isinstance(item, BaseObject)]:
                target_state = self.states.get(target.id)
                target_position = target_state.position if target_state else target.position
                inside = math.dist(state.position, target_position) <= self._region_radius(target)
                key = (ball.id, target.id)
                if key not in self._inside_regions:
                    self._inside_regions[key] = inside
                    continue
                was_inside = self._inside_regions[key]
                self._inside_regions[key] = inside
                if ball.duplication_trigger == DuplicationTrigger.ENTER_REGION and not was_inside and inside:
                    self._attempt_duplicate(ball)
                elif ball.duplication_trigger == DuplicationTrigger.LEAVE_RING and isinstance(target, RingObject) and was_inside and not inside:
                    self._attempt_duplicate(ball)

    def _update_scheduled_duplications(self, previous_time: float, current_time: float) -> None:
        for ball in [model for model in list(self.models.values()) if isinstance(model, BallObject)]:
            if ball.duplication_trigger == DuplicationTrigger.INTERVAL:
                interval = max(self.fixed_dt, ball.duplication_interval_seconds)
            elif ball.duplication_trigger == DuplicationTrigger.BEAT:
                tempo = max(0.05, self.project.midi_playback.tempo_multiplier)
                interval = max(self.fixed_dt, 0.5 * max(0.0625, ball.duplication_beat_interval) / tempo)
            else:
                continue
            previous_index = math.floor((previous_time + 1e-9) / interval)
            current_index = math.floor((current_time + 1e-9) / interval)
            for _ in range(min(4, max(0, current_index - previous_index))):
                if not self._attempt_duplicate(ball):
                    break

    def _duplicate_spawn_position(
        self, parent: BallObject, clone: BallObject, batch_index: int = 0, batch_count: int = 1
    ) -> tuple[float, float]:
        state = self.states[parent.id]
        mode = parent.duplication_spawn_mode
        target = self.models.get(parent.duplication_spawn_target_id or "")
        if mode == DuplicationSpawnMode.ORIGINAL_POSITION:
            center = parent.position
        elif mode == DuplicationSpawnMode.SELECTED_OBJECT_CENTER and isinstance(target, BaseObject):
            target_state = self.states.get(target.id)
            center = target_state.position if target_state else target.position
        elif mode == DuplicationSpawnMode.CUSTOM_POSITION:
            center = parent.duplication_spawn_position
        else:
            center = state.position

        spread = max(0.0, parent.duplication_spawn_spread)
        if isinstance(target, RingObject) and mode == DuplicationSpawnMode.SELECTED_OBJECT_CENTER:
            safe_radius = max(0.0, target.radius - target.thickness / 2.0 - clone.radius - 4.0)
            spread = min(spread, safe_radius)
        if spread > 0.0:
            if batch_count > 1:


                parent_state = self.states[parent.id]
                seed = self.project.scene.physics.deterministic_seed
                phase_seed = (
                    seed * 1_000_003
                    + parent.generation * 104_729
                    + self._duplicate_counts[parent.id] * 7_919
                    + round(parent_state.position[0] * 10.0) * 193
                    + round(parent_state.position[1] * 10.0) * 389
                )
                phase = random.Random(phase_seed).random() * math.tau
                angle = phase + batch_index * 2.399963229728653
                radius = spread * math.sqrt((batch_index + 0.5) / batch_count)
            else:
                angle = self.rng.random() * math.tau
                radius = spread * math.sqrt(self.rng.random())
            center = (center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius)
        elif mode == DuplicationSpawnMode.COLLISION_POSITION:
            center = (center[0] + self.rng.uniform(-8.0, 8.0), center[1] + self.rng.uniform(-8.0, 8.0))
        return center

    def _duplicate_base_velocity(self, parent: BallObject) -> tuple[float, float]:
        state = self.states[parent.id]
        if parent.duplication_velocity_mode == DuplicationVelocityMode.INITIAL:
            return parent.initial_velocity
        if parent.duplication_velocity_mode == DuplicationVelocityMode.RANDOM_DIRECTION:
            speed = max(80.0, math.hypot(*state.velocity) or math.hypot(*parent.initial_velocity))
            angle = self.rng.random() * math.tau
            return (math.cos(angle) * speed, math.sin(angle) * speed)
        return state.velocity

    def _configure_clone(
        self, parent: BallObject, batch_index: int = 0, batch_count: int = 1
    ) -> BallObject:
        clone = copy.deepcopy(parent)
        clone.id = new_id("ball")
        event_number = self._duplicate_counts[parent.id]
        clone.name = (
            f"{parent.name} {event_number}.{batch_index + 1}"
            if batch_count > 1
            else f"{parent.name} {event_number}"
        )
        clone.generation = parent.generation + 1
        if parent.remove_source_after_duplication and parent.reset_generation_on_respawn:
            clone.generation = 0
        if parent.duplication_mode == DuplicationMode.SIZE_VARIATION:
            clone.radius = max(4.0, parent.radius * self.rng.uniform(1 - parent.duplicate_size_variation, 1 + parent.duplicate_size_variation))
        clone.position = self._duplicate_spawn_position(parent, clone, batch_index, batch_count)
        vx, vy = self._duplicate_base_velocity(parent)
        if parent.duplication_mode in {DuplicationMode.VELOCITY_VARIATION, DuplicationMode.PALETTE_PROGRESSION}:
            angle = math.atan2(vy, vx) + self.rng.uniform(-0.6, 0.6) * parent.duplicate_velocity_variation
            speed = max(80.0, math.hypot(vx, vy) * self.rng.uniform(0.85, 1.15))
            clone.initial_velocity = (math.cos(angle) * speed, math.sin(angle) * speed)
        else:
            clone.initial_velocity = (vx, vy)
        if parent.duplication_mode == DuplicationMode.DIFFERENT_TRACK and self.project.selected_track_ids:
            current = parent.midi_track_ids[0] if parent.midi_track_ids else self.project.selected_track_ids[0]
            index = self.project.selected_track_ids.index(current) if current in self.project.selected_track_ids else -1
            clone.midi_track_ids = [self.project.selected_track_ids[(index + 1) % len(self.project.selected_track_ids)]]
        if parent.duplication_mode == DuplicationMode.NEXT_CHANNEL:
            clone.midi_channel = ((parent.midi_channel or 0) + 1) % 16
        if parent.duplication_mode == DuplicationMode.PALETTE_PROGRESSION:
            clone.color = self._color_for(parent)
        return clone

    def _spawn_duplicate(
        self, parent: BallObject, batch_index: int = 0, batch_count: int = 1
    ) -> None:
        raise NotImplementedError

    def _update_emitters(self, dt: float) -> None:
        for model in list(self.models.values()):
            if not isinstance(model, EmitterObject) or not model.enabled:
                continue
            runtime = self._emitter_runtime[model.id]
            if not runtime.initialized:
                runtime.initialized = True
                for _ in range(max(0, model.initial_ball_count)):
                    self._spawn_emitter_ball(model, runtime)
            runtime.elapsed += dt
            interval = max(0.01, model.spawn_interval)
            while runtime.elapsed >= interval:
                runtime.elapsed -= interval
                self._spawn_emitter_ball(model, runtime)

    def _spawn_emitter_ball(self, emitter: EmitterObject, runtime: _EmitterRuntime) -> None:
        active_balls = sum(isinstance(model, BallObject) for model in self.models.values())
        if active_balls >= min(emitter.maximum_ball_count, self.project.scene.physics.max_balls):
            return
        local_rng = random.Random(emitter.random_seed + runtime.spawned)
        width, height = emitter.spawn_area
        position = (
            emitter.position[0] + local_rng.uniform(-width / 2, width / 2),
            emitter.position[1] + local_rng.uniform(-height / 2, height / 2),
        )
        radius = local_rng.uniform(*sorted(emitter.radius_range))
        speed = local_rng.uniform(*sorted(emitter.speed_range))
        direction = math.radians(local_rng.uniform(*sorted(emitter.direction_range)))
        lifetime = local_rng.uniform(*sorted(emitter.lifetime_range)) if max(emitter.lifetime_range) > 0 else 0.0
        ball = BallObject(
            id=new_id("ball"),
            name=f"{emitter.name} Ball {runtime.spawned + 1}",
            position=position,
            radius=radius,
            initial_velocity=(math.cos(direction) * speed, math.sin(direction) * speed),
            color=self.project.scene.palette.colors[runtime.spawned % len(self.project.scene.palette.colors)],
            midi_track_ids=(
                [self.project.selected_track_ids[runtime.spawned % len(self.project.selected_track_ids)]]
                if self.project.selected_track_ids else []
            ),
            lifetime_seconds=lifetime,
        )
        runtime.spawned += 1
        self._spawn_runtime_ball(ball)
        event = PhysicsEvent(
            self.time, "ball_creation", ball.id, emitter.id, ball.position, 0.0,
            {"source": "emitter", "emitter": emitter.id},
        )
        self.physics_events.append(event)
        if self.event_callback:
            self.event_callback(event)

    def _spawn_runtime_ball(self, ball: BallObject) -> None:
        raise NotImplementedError

    def _remove_runtime_object(self, object_id: str) -> None:
        model = self.models.get(object_id)
        state = self.states.get(object_id)
        if model is not None:
            event_type = "ball_deletion" if isinstance(model, BallObject) else "object_deletion"
            event = PhysicsEvent(
                self.time, event_type, object_id, "",
                state.position if state else model.position, 0.0,
                {"kind": model.kind.value},
            )
            self.physics_events.append(event)
            if self.event_callback:
                self.event_callback(event)
        self.models.pop(object_id, None)
        self.states.pop(object_id, None)
        self.trails.pop(object_id, None)
        self._spawn_times.pop(object_id, None)
        for key in [key for key in self._inside_regions if object_id in key]:
            self._inside_regions.pop(key, None)

    def _flush_pending_removals(self) -> None:
        for object_id in list(self._pending_removals):
            self._pending_removals.discard(object_id)
            if object_id in self.models:
                self._remove_runtime_object(object_id)

    def set_object_position(self, object_id: str, position: tuple[float, float]) -> None:
        model = self.models.get(object_id)
        if model:
            model.position = position
        state = self.states.get(object_id)
        if state:
            state.position = position

    def snapshot(self) -> SimulationSnapshot:
        return SimulationSnapshot(
            time=self.time,
            frame=self.frame,
            collision_count=self.collision_count,
            active_ball_count=sum(isinstance(model, BallObject) for model in self.models.values()),
            object_states={key: copy.deepcopy(value) for key, value in self.states.items()},
            particles=copy.deepcopy(self.particles),
            ripples=copy.deepcopy(self.ripples),
            current_notes=[pitch for _, pitch in self.active_notes],
            dropped_frames=self.dropped_frames,
            physics_hz=self.project.scene.physics.physics_hz,
            camera_shake=self.camera_shake,
        )


class _PymunkBackend(_BackendBase):
    def __init__(self, project, note_callback, event_callback) -> None:
        if pymunk is None:
            raise SimulationUnavailableError("Pymunk is not installed.")
        super().__init__(project, note_callback, event_callback)
        self.space = None
        self.bodies: dict[str, object] = {}
        self.shapes: dict[str, list[object]] = defaultdict(list)
        self._ring_rebuild_elapsed = 0.0
        self._space_stepping = False
        self.reset()

    def reset(self) -> None:
        super().reset()
        self._space_stepping = False
        self.space = pymunk.Space(threaded=False)
        self.space.gravity = self.project.scene.physics.gravity
        self.space.damping = self.project.scene.physics.air_resistance
        self.space.iterations = self.project.scene.physics.collision_iterations
        self.bodies.clear()
        self.shapes.clear()
        self.space.on_collision(None, None, begin=self._on_begin, post_solve=self._on_post_solve)
        if self.project.scene.physics.world_boundaries and not self.project.scene.physics.wraparound:
            self._add_world_boundaries()
        for model in list(self.models.values()):
            self._add_model(model)

    def _tag(self, shape, model_id: str, kind: str) -> None:
        shape.bb_id = model_id
        shape.bb_kind = kind

    def _add_world_boundaries(self) -> None:
        width, height = self.project.scene.logical_width, self.project.scene.logical_height
        body = self.space.static_body
        points = [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            shape = pymunk.Segment(body, start, end, 8.0)
            shape.set_neighbors(points[(index - 1) % len(points)], points[(index + 2) % len(points)])
            shape.elasticity = self.project.scene.physics.global_restitution
            shape.friction = self.project.scene.physics.global_friction
            self._tag(shape, f"world_{index}", "world")
            self.space.add(shape)

    def _add_model(self, model: SceneObject) -> None:
        if not model.visible:
            return
        if isinstance(model, BallObject):
            self._spawn_runtime_ball(model)
        elif isinstance(model, WallObject):
            shape = pymunk.Segment(self.space.static_body, model.start, model.end, model.thickness / 2)
            shape.elasticity = model.restitution
            shape.friction = model.friction
            self._tag(shape, model.id, model.kind.value)
            self.space.add(shape)
            self.shapes[model.id].append(shape)
            self.states[model.id] = RuntimeObjectState(model.id, model.position, model.rotation, color=model.color)
        elif isinstance(model, RingObject):
            self._add_ring(model)
        elif isinstance(model, BumperObject):
            shape = pymunk.Circle(self.space.static_body, model.radius, offset=model.position)
            shape.elasticity = model.restitution
            shape.friction = 0.2
            self._tag(shape, model.id, model.kind.value)
            self.space.add(shape)
            self.shapes[model.id].append(shape)
            self.states[model.id] = RuntimeObjectState(model.id, model.position, model.rotation, radius=model.radius, color=model.color)
        elif isinstance(model, PolygonObject):
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = model.position
            body.angle = math.radians(model.rotation)
            body.angular_velocity = math.radians(model.rotation_speed)
            shape = pymunk.Poly(body, model.vertices)
            shape.elasticity = model.restitution
            shape.friction = model.friction
            self._tag(shape, model.id, model.kind.value)
            self.space.add(body, shape)
            self.bodies[model.id] = body
            self.shapes[model.id].append(shape)
            self.states[model.id] = RuntimeObjectState(model.id, model.position, model.rotation, color=model.color)
        elif isinstance(model, PortalObject):
            shape = pymunk.Circle(self.space.static_body, model.radius, offset=model.position)
            shape.sensor = True
            self._tag(shape, model.id, model.kind.value)
            self.space.add(shape)
            self.shapes[model.id].append(shape)
            self.states[model.id] = RuntimeObjectState(model.id, model.position, model.rotation, radius=model.radius, color=model.color)
        else:
            self.states[model.id] = RuntimeObjectState(model.id, model.position, model.rotation, color=model.color)

    def _add_ring(
        self,
        model: RingObject,
        *,
        body_angle: float | None = None,
        angular_velocity: float | None = None,
    ) -> None:
        if model.collision_mode == "disabled":
            rotation = model.rotation + model.opening_rotation
            self.states[model.id] = RuntimeObjectState(
                model.id, model.position, rotation, radius=model.radius, color=model.color
            )
            return

        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = model.position
        body.angle = math.radians(model.rotation + model.opening_rotation) if body_angle is None else body_angle
        body.angular_velocity = (
            math.radians(model.rotation_speed) if angular_velocity is None else angular_velocity
        )
        self.space.add(body)
        self.bodies[model.id] = body


        for geometry in ring_arc_segments(model.radius, model.opening_angle, model.segments):
            shape = pymunk.Segment(body, geometry.start, geometry.end, max(0.5, model.thickness / 2.0))
            shape.set_neighbors(geometry.previous, geometry.following)
            shape.elasticity = self.project.scene.physics.global_restitution
            shape.friction = self.project.scene.physics.global_friction
            shape.sensor = model.collision_mode == "trigger"
            self._tag(shape, model.id, model.kind.value)
            self.space.add(shape)
            self.shapes[model.id].append(shape)

        self.states[model.id] = RuntimeObjectState(
            model.id, model.position, math.degrees(body.angle), radius=model.radius, color=model.color
        )

    def _spawn_runtime_ball(self, ball: BallObject) -> None:
        self.models[ball.id] = ball
        self._spawn_times[ball.id] = self.time
        moment = pymunk.moment_for_circle(max(0.001, ball.mass), 0, ball.radius)
        body = pymunk.Body(max(0.001, ball.mass), moment)
        body.position = ball.position
        body.velocity = ball.initial_velocity
        body.angle = math.radians(ball.rotation)
        body.angular_velocity = math.radians(ball.angular_velocity)
        gravity_scale = ball.gravity_scale

        def velocity_func(target_body, gravity, damping, dt):
            pymunk.Body.update_velocity(target_body, gravity * gravity_scale, damping, dt)

        body.velocity_func = velocity_func
        shape = pymunk.Circle(body, ball.radius)
        shape.elasticity = ball.restitution
        shape.friction = ball.friction
        self._tag(shape, ball.id, ball.kind.value)
        self.space.add(body, shape)
        self.bodies[ball.id] = body
        self.shapes[ball.id].append(shape)
        self.trails[ball.id] = deque(maxlen=max(1, ball.trail_length))
        self.states[ball.id] = RuntimeObjectState(
            ball.id, ball.position, ball.rotation, ball.initial_velocity, ball.radius, ball.color
        )

    def _spawn_duplicate(
        self, parent: BallObject, batch_index: int = 0, batch_count: int = 1
    ) -> None:
        self._spawn_runtime_ball(self._configure_clone(parent, batch_index, batch_count))

    def _on_begin(self, arbiter, _space, _data):
        shapes = arbiter.shapes
        a_id, b_id = getattr(shapes[0], "bb_id", ""), getattr(shapes[1], "bb_id", "")
        a_model, b_model = self.models.get(a_id), self.models.get(b_id)
        if isinstance(a_model, PortalObject) and isinstance(b_model, BallObject):
            body = self.bodies.get(b_model.id)
            strength = float(body.velocity.length * b_model.mass) if body is not None else 0.0
            self._register_collision(b_model, a_model, self.states[b_model.id].position, strength)
            self._teleport(b_model, a_model)
        elif isinstance(b_model, PortalObject) and isinstance(a_model, BallObject):
            body = self.bodies.get(a_model.id)
            strength = float(body.velocity.length * a_model.mass) if body is not None else 0.0
            self._register_collision(a_model, b_model, self.states[a_model.id].position, strength)
            self._teleport(a_model, b_model)
        else:
            ball = a_model if isinstance(a_model, BallObject) else b_model if isinstance(b_model, BallObject) else None
            surface = b_model if ball is a_model else a_model
            if ball is not None and isinstance(surface, RingObject) and surface.collision_mode == "trigger":
                body = self.bodies.get(ball.id)
                strength = float(body.velocity.length * ball.mass) if body is not None else 0.0
                self._register_collision(ball, surface, self.states[ball.id].position, strength)
                if surface.break_on_hit and strength >= surface.break_strength:
                    self._pending_removals.add(surface.id)

    def _teleport(self, ball: BallObject, portal: PortalObject) -> None:
        if self.time - self._portal_last_time.get(ball.id, -999) < portal.cooldown_ms / 1000.0:
            return
        target = self.models.get(portal.target_portal_id or "")
        body = self.bodies.get(ball.id)
        if not isinstance(target, PortalObject) or body is None:
            return
        velocity = body.velocity
        direction = normalized((float(velocity.x), float(velocity.y)), (1.0, 0.0))
        body.position = add(target.position, multiply(direction, target.radius + ball.radius + 2.0))
        if portal.preserve_velocity:
            body.velocity = velocity * portal.exit_speed_multiplier
        else:
            body.velocity = (0.0, 0.0)
        self._portal_last_time[ball.id] = self.time
        event = PhysicsEvent(self.time, "portal", ball.id, portal.id, tuple(body.position), 0.0)
        self.physics_events.append(event)
        if self.event_callback:
            self.event_callback(event)

    def _on_post_solve(self, arbiter, _space, _data):
        if not arbiter.is_first_contact:
            return
        shape_a, shape_b = arbiter.shapes
        a_id, b_id = getattr(shape_a, "bb_id", ""), getattr(shape_b, "bb_id", "")
        a_model, b_model = self.models.get(a_id), self.models.get(b_id)
        strength = float(arbiter.total_impulse.length)
        points = arbiter.contact_point_set.points
        if points:
            point_a = points[0].point_a
            point_b = points[0].point_b
            position = ((float(point_a.x) + float(point_b.x)) / 2.0, (float(point_a.y) + float(point_b.y)) / 2.0)
        else:
            position = (0.0, 0.0)

        if isinstance(a_model, BallObject) and isinstance(b_model, BallObject):
            if not points:
                first_state = self.states.get(a_model.id)
                second_state = self.states.get(b_model.id)
                if first_state and second_state:
                    position = (
                        (first_state.position[0] + second_state.position[0]) / 2.0,
                        (first_state.position[1] + second_state.position[1]) / 2.0,
                    )
            self._register_ball_pair_collision(a_model, b_model, position, strength)
            return

        ball = a_model if isinstance(a_model, BallObject) else b_model if isinstance(b_model, BallObject) else None
        surface = b_model if ball is a_model else a_model
        if ball is None:
            return
        if not points:
            position = self.states[ball.id].position
        self._register_collision(ball, surface, position, strength)

        if isinstance(surface, BumperObject) and surface.impulse > 0:
            body = self.bodies.get(ball.id)
            if body is not None:
                direction = normalized((float(body.position.x) - surface.position[0], float(body.position.y) - surface.position[1]))
                body.apply_impulse_at_world_point(
                    (direction[0] * surface.impulse * max(0.001, ball.mass),
                     direction[1] * surface.impulse * max(0.001, ball.mass)),
                    body.position,
                )

        if surface and getattr(surface, "break_on_hit", False) and strength >= getattr(surface, "break_strength", math.inf):
            self._pending_removals.add(surface.id)

    def _remove_pymunk_object(self, object_id: str) -> None:
        if self._space_stepping:
            self._pending_removals.add(object_id)
            return
        body = self.bodies.pop(object_id, None)
        shapes = self.shapes.pop(object_id, [])
        removable = [*shapes]
        if body is not None:
            removable.append(body)
        if removable:
            self.space.remove(*removable)
        self._remove_runtime_object(object_id)

    def _rebuild_ring(self, model: RingObject) -> None:
        body = self.bodies.pop(model.id, None)
        body_angle = float(body.angle) if body is not None else math.radians(model.rotation + model.opening_rotation)
        angular_velocity = float(body.angular_velocity) if body is not None else math.radians(model.rotation_speed)
        shapes = self.shapes.pop(model.id, [])
        removable = [*shapes]
        if body is not None:
            removable.append(body)
        if removable:
            self.space.remove(*removable)


        self._add_ring(model, body_angle=body_angle, angular_velocity=angular_velocity)

    def _attempt_duplicate(self, ball: BallObject) -> bool:
        if not self._space_stepping:
            return super()._attempt_duplicate(ball)
        if ball.id in self._pending_duplicate_ids:
            return False
        reserved = sum(
            self._pending_net_growth(pending_ball)
            for pending_id in self._pending_duplicate_ids
            if isinstance((pending_ball := self.models.get(pending_id)), BallObject)
        )
        if not self._can_duplicate(ball, reserved=reserved):
            return False
        self._pending_duplicate_ids.add(ball.id)
        return True

    def _flush_pending_duplications(self) -> None:
        pending = list(self._pending_duplicate_ids)
        self._pending_duplicate_ids.clear()
        for object_id in pending:
            ball = self.models.get(object_id)
            if isinstance(ball, BallObject):
                super()._attempt_duplicate(ball)

    def _flush_pending_removals(self) -> None:
        for object_id in list(self._pending_removals):
            self._pending_removals.discard(object_id)
            if object_id in self.models:
                self._remove_pymunk_object(object_id)

    def set_object_position(self, object_id: str, position: tuple[float, float]) -> None:
        super().set_object_position(object_id, position)
        body = self.bodies.get(object_id)
        if body is not None:
            body.position = position
        elif object_id in self.shapes:
            self.reset()

    def _effective_substeps(self, step_dt: float) -> int:
        settings = self.project.scene.physics
        configured = max(1, settings.substeps)
        if not settings.continuous_collision_detection:
            return configured

        smallest_feature = math.inf
        maximum_ball_speed = 0.0
        maximum_surface_speed = 0.0
        for object_id, model in self.models.items():
            if isinstance(model, BallObject):
                body = self.bodies.get(object_id)
                speed = float(body.velocity.length) if body is not None else math.hypot(*model.initial_velocity)
                maximum_ball_speed = max(maximum_ball_speed, speed)
                smallest_feature = min(smallest_feature, max(1.0, model.radius))
            elif isinstance(model, WallObject):
                smallest_feature = min(smallest_feature, max(1.0, model.thickness / 2.0))
            elif isinstance(model, RingObject):
                smallest_feature = min(smallest_feature, max(1.0, model.thickness / 2.0))
                maximum_surface_speed = max(
                    maximum_surface_speed,
                    abs(math.radians(model.rotation_speed)) * max(1.0, model.radius),
                )
            elif isinstance(model, PolygonObject):
                smallest_feature = min(smallest_feature, minimum_polygon_half_width(model.vertices))
                extent = max((math.hypot(x, y) for x, y in model.vertices), default=1.0)
                maximum_surface_speed = max(
                    maximum_surface_speed,
                    abs(math.radians(model.rotation_speed)) * extent,
                )
            elif isinstance(model, BumperObject):
                smallest_feature = min(smallest_feature, max(1.0, model.radius))

        if not math.isfinite(smallest_feature):
            return configured
        travel = (maximum_ball_speed + maximum_surface_speed) * step_dt * settings.simulation_speed
        allowed_travel = max(1.0, smallest_feature * 0.35)
        required = max(1, math.ceil(travel / allowed_travel))
        return min(max(configured, required), max(configured, settings.max_collision_substeps))

    def step(self, dt: float | None = None) -> SimulationSnapshot:
        step_dt = self.fixed_dt if dt is None else dt
        previous_time = self.time
        self._update_emitters(step_dt)
        substeps = self._effective_substeps(step_dt)
        physics_dt = step_dt * self.project.scene.physics.simulation_speed / substeps
        for _ in range(substeps):
            self._space_stepping = True
            try:
                self.space.step(physics_dt)
            finally:
                self._space_stepping = False


            self._flush_pending_duplications()
            self._flush_pending_removals()
        self.time += step_dt
        self.frame += 1
        self._ring_rebuild_elapsed += step_dt

        for object_id, body in list(self.bodies.items()):
            model = self.models.get(object_id)
            state = self.states.get(object_id)
            if state is None:
                continue
            state.position = (float(body.position.x), float(body.position.y))
            state.rotation = math.degrees(float(body.angle))
            if isinstance(model, BallObject):
                speed = float(body.velocity.length)
                limit = min(model.maximum_speed, self.project.scene.physics.maximum_speed)
                if speed > limit > 0:
                    body.velocity = body.velocity.normalized() * limit
                state.velocity = (float(body.velocity.x), float(body.velocity.y))
                if self.project.scene.physics.wraparound:
                    width, height = self.project.scene.logical_width, self.project.scene.logical_height
                    wrapped = (state.position[0] % width, state.position[1] % height)
                    if wrapped != state.position:
                        body.position = wrapped
                        state.position = wrapped
                trail = self.trails[object_id]
                if model.trail_enabled:
                    trail.append(state.position)
                    state.trail = list(trail)
                if model.lifetime_seconds > 0 and self.time - self._spawn_times.get(object_id, 0.0) >= model.lifetime_seconds:
                    self._remove_pymunk_object(object_id)
            elif isinstance(model, RingObject):
                state.radius = model.radius
                model.rotation = state.rotation - model.opening_rotation


        for model in list(self.models.values()):
            if isinstance(model, RingObject) and model.collision_mode == "disabled":
                state = self.states.get(model.id)
                if state is not None:
                    state.rotation += model.rotation_speed * step_dt * self.project.scene.physics.simulation_speed
                    model.rotation = state.rotation - model.opening_rotation

        if self._ring_rebuild_elapsed >= 1 / 30:
            elapsed = self._ring_rebuild_elapsed
            self._ring_rebuild_elapsed = 0.0
            for model in list(self.models.values()):
                if isinstance(model, RingObject) and model.expand_rate:
                    model.radius += model.expand_rate * elapsed * self.project.scene.physics.simulation_speed
                    if model.radius > model.maximum_radius:
                        model.radius = model.minimum_radius
                    elif model.radius < model.minimum_radius:
                        model.radius = model.maximum_radius
                    self._rebuild_ring(model)

        self._update_scheduled_duplications(previous_time, self.time)
        self._update_spatial_duplications()
        self._flush_pending_removals()
        self._timeline_notes(previous_time, self.time)
        self._update_effects(step_dt)
        return self.snapshot()


class _FallbackBackend(_BackendBase):
    """Deterministic pure-Python physics used when Pymunk cannot be imported.

    It intentionally mirrors every editor collision shape. The fallback is not as
    fast as Chipmunk, but it no longer silently ignores walls, rings, polygons, or
    ball-to-ball collisions.
    """

    def __init__(self, project, note_callback, event_callback) -> None:
        self.velocities: dict[str, tuple[float, float]] = {}
        super().__init__(project, note_callback, event_callback)
        self.reset()

    def reset(self) -> None:
        super().reset()
        self.velocities.clear()
        for model in self.models.values():
            if isinstance(model, BallObject):
                self._spawn_runtime_ball(model)
            else:
                radius = getattr(model, "radius", 0.0)
                rotation = model.rotation + model.opening_rotation if isinstance(model, RingObject) else model.rotation
                self.states[model.id] = RuntimeObjectState(
                    model.id, model.position, rotation, radius=radius, color=model.color
                )

    def _spawn_runtime_ball(self, ball: BallObject) -> None:
        self.models[ball.id] = ball
        self._spawn_times[ball.id] = self.time
        self.velocities[ball.id] = ball.initial_velocity
        self.trails[ball.id] = deque(maxlen=max(1, ball.trail_length))
        self.states[ball.id] = RuntimeObjectState(
            ball.id, ball.position, ball.rotation, ball.initial_velocity, ball.radius, ball.color
        )

    def _spawn_duplicate(
        self, parent: BallObject, batch_index: int = 0, batch_count: int = 1
    ) -> None:
        self._spawn_runtime_ball(self._configure_clone(parent, batch_index, batch_count))

    def _remove_runtime_object(self, object_id: str) -> None:
        super()._remove_runtime_object(object_id)
        self.velocities.pop(object_id, None)

    def _effective_substeps(self, step_dt: float) -> int:
        settings = self.project.scene.physics
        configured = max(1, settings.substeps)
        if not settings.continuous_collision_detection:
            return configured
        smallest_feature = math.inf
        maximum_ball_speed = 0.0
        maximum_surface_speed = 0.0
        for model in self.models.values():
            if isinstance(model, BallObject):
                maximum_ball_speed = max(maximum_ball_speed, math.hypot(*self.velocities.get(model.id, model.initial_velocity)))
                smallest_feature = min(smallest_feature, max(1.0, model.radius))
            elif isinstance(model, WallObject):
                smallest_feature = min(smallest_feature, max(1.0, model.thickness / 2.0))
            elif isinstance(model, RingObject):
                smallest_feature = min(smallest_feature, max(1.0, model.thickness / 2.0))
                maximum_surface_speed = max(
                    maximum_surface_speed,
                    abs(math.radians(model.rotation_speed)) * max(1.0, model.radius),
                )
            elif isinstance(model, PolygonObject):
                smallest_feature = min(smallest_feature, minimum_polygon_half_width(model.vertices))
                extent = max((math.hypot(x, y) for x, y in model.vertices), default=1.0)
                maximum_surface_speed = max(
                    maximum_surface_speed,
                    abs(math.radians(model.rotation_speed)) * extent,
                )
            elif isinstance(model, BumperObject):
                smallest_feature = min(smallest_feature, max(1.0, model.radius))
        if not math.isfinite(smallest_feature):
            return configured
        travel = (maximum_ball_speed + maximum_surface_speed) * step_dt * settings.simulation_speed
        allowed_travel = max(1.0, smallest_feature * 0.35)
        required = max(1, math.ceil(travel / allowed_travel))
        return min(max(configured, required), max(configured, settings.max_collision_substeps))

    def _apply_surface_response(
        self,
        ball: BallObject,
        state: RuntimeObjectState,
        surface: BaseObject,
        normal: tuple[float, float],
        penetration: float,
        contact: tuple[float, float],
        restitution: float,
        friction: float,
        surface_velocity: tuple[float, float] = (0.0, 0.0),
        sensor: bool = False,
        extra_impulse: float = 0.0,
    ) -> float:
        normal = normalized(normal)
        velocity = self.velocities[ball.id]
        relative = subtract(velocity, surface_velocity)
        normal_speed = dot(relative, normal)
        strength = max(0.0, -normal_speed) * max(0.001, ball.mass)

        if not sensor:
            correction = max(0.0, penetration) + max(0.0, self.project.scene.physics.collision_skin) * 0.02
            state.position = add(state.position, multiply(normal, correction))
            if normal_speed < 0.0:
                bounced = subtract(relative, multiply(normal, (1.0 + restitution) * normal_speed))
                tangent = subtract(bounced, multiply(normal, dot(bounced, normal)))
                friction_factor = max(0.0, 1.0 - max(0.0, friction) * 0.08)
                bounced = add(multiply(normal, dot(bounced, normal)), multiply(tangent, friction_factor))
                velocity = add(surface_velocity, bounced)
                if extra_impulse > 0.0:
                    velocity = add(velocity, multiply(normal, extra_impulse))
            self.velocities[ball.id] = velocity
            state.velocity = velocity

        self._register_collision(ball, surface, contact, strength)
        if getattr(surface, "break_on_hit", False) and strength >= getattr(surface, "break_strength", math.inf):
            self._remove_runtime_object(surface.id)
        return strength

    def _resolve_segment_surface(
        self,
        ball: BallObject,
        state: RuntimeObjectState,
        surface: BaseObject,
        start: tuple[float, float],
        end: tuple[float, float],
        shape_radius: float,
        restitution: float,
        friction: float,
        *,
        surface_velocity: tuple[float, float] = (0.0, 0.0),
        sensor: bool = False,
    ) -> bool:
        contact, _ = closest_point_on_segment(state.position, start, end)
        delta = subtract(state.position, contact)
        distance = length(delta)
        minimum = ball.radius + max(0.0, shape_radius)
        if distance >= minimum:
            return False
        relative = subtract(self.velocities[ball.id], surface_velocity)
        normal = normalized(delta, normalized(multiply(relative, -1.0)))
        self._apply_surface_response(
            ball,
            state,
            surface,
            normal,
            minimum - distance,
            contact,
            restitution,
            friction,
            surface_velocity,
            sensor,
        )
        return True

    def _resolve_ring(self, ball: BallObject, state: RuntimeObjectState, ring: RingObject) -> bool:
        if ring.collision_mode == "disabled":
            return False
        ring_state = self.states.get(ring.id)
        rotation = ring_state.rotation if ring_state else ring.rotation + ring.opening_rotation
        best: tuple[float, tuple[float, float], tuple[float, float], tuple[float, float]] | None = None
        for geometry in ring_arc_segments(ring.radius, ring.opening_angle, ring.segments):
            start = transform_point(geometry.start, ring.position, rotation)
            end = transform_point(geometry.end, ring.position, rotation)
            contact, _ = closest_point_on_segment(state.position, start, end)
            distance = length(subtract(state.position, contact))
            if best is None or distance < best[0]:
                best = (distance, contact, start, end)
        if best is None:
            return False
        distance, contact, start, end = best
        minimum = ball.radius + max(0.5, ring.thickness / 2.0)
        if distance >= minimum:
            return False
        surface_velocity = angular_velocity_at(contact, ring.position, ring.rotation_speed)
        delta = subtract(state.position, contact)
        relative = subtract(self.velocities[ball.id], surface_velocity)
        normal = normalized(delta, normalized(multiply(relative, -1.0)))
        self._apply_surface_response(
            ball,
            state,
            ring,
            normal,
            minimum - distance,
            contact,
            self.project.scene.physics.global_restitution,
            self.project.scene.physics.global_friction,
            surface_velocity,
            ring.collision_mode == "trigger",
        )
        return True

    def _resolve_bumper(self, ball: BallObject, state: RuntimeObjectState, bumper: BumperObject) -> bool:
        delta = subtract(state.position, bumper.position)
        distance = length(delta)
        minimum = ball.radius + bumper.radius
        if distance >= minimum:
            return False
        normal = normalized(delta, normalized(multiply(self.velocities[ball.id], -1.0)))
        contact = add(bumper.position, multiply(normal, bumper.radius))
        self._apply_surface_response(
            ball,
            state,
            bumper,
            normal,
            minimum - distance,
            contact,
            bumper.restitution,
            0.2,
            extra_impulse=bumper.impulse,
        )
        return True

    def _resolve_polygon(self, ball: BallObject, state: RuntimeObjectState, polygon: PolygonObject) -> bool:
        polygon_state = self.states.get(polygon.id)
        rotation = polygon_state.rotation if polygon_state else polygon.rotation
        vertices = polygon_world_vertices(polygon.vertices, polygon.position, rotation)
        if len(vertices) < 2:
            return False
        inside = point_in_polygon(state.position, vertices)
        best_distance = math.inf
        best_contact = vertices[0]
        for index, start in enumerate(vertices):
            end = vertices[(index + 1) % len(vertices)]
            contact, _ = closest_point_on_segment(state.position, start, end)
            distance = length(subtract(state.position, contact))
            if distance < best_distance:
                best_distance = distance
                best_contact = contact
        if not inside and best_distance >= ball.radius:
            return False
        if inside:
            normal = normalized(subtract(best_contact, state.position), normalized(multiply(self.velocities[ball.id], -1.0)))
            penetration = ball.radius + best_distance
        else:
            normal = normalized(subtract(state.position, best_contact), normalized(multiply(self.velocities[ball.id], -1.0)))
            penetration = ball.radius - best_distance
        surface_velocity = angular_velocity_at(best_contact, polygon.position, polygon.rotation_speed)
        self._apply_surface_response(
            ball,
            state,
            polygon,
            normal,
            penetration,
            best_contact,
            polygon.restitution,
            polygon.friction,
            surface_velocity,
        )
        return True

    def _resolve_ball_pair(self, first: BallObject, second: BallObject) -> bool:
        first_state = self.states.get(first.id)
        second_state = self.states.get(second.id)
        if first_state is None or second_state is None:
            return False
        delta = subtract(second_state.position, first_state.position)
        distance = length(delta)
        minimum = first.radius + second.radius
        if distance >= minimum:
            return False
        relative_velocity = subtract(self.velocities[second.id], self.velocities[first.id])
        normal = normalized(delta, normalized(relative_velocity))
        inverse_first = 1.0 / max(0.001, first.mass)
        inverse_second = 1.0 / max(0.001, second.mass)
        inverse_total = inverse_first + inverse_second
        penetration = minimum - distance
        first_state.position = subtract(first_state.position, multiply(normal, penetration * inverse_first / inverse_total))
        second_state.position = add(second_state.position, multiply(normal, penetration * inverse_second / inverse_total))

        speed_along_normal = dot(relative_velocity, normal)
        impulse_magnitude = 0.0
        if speed_along_normal < 0.0:
            restitution = min(first.restitution, second.restitution)
            impulse_magnitude = -(1.0 + restitution) * speed_along_normal / inverse_total
            impulse = multiply(normal, impulse_magnitude)
            self.velocities[first.id] = subtract(self.velocities[first.id], multiply(impulse, inverse_first))
            self.velocities[second.id] = add(self.velocities[second.id], multiply(impulse, inverse_second))
            first_state.velocity = self.velocities[first.id]
            second_state.velocity = self.velocities[second.id]
        contact = add(first_state.position, multiply(normal, first.radius))
        self._register_ball_pair_collision(first, second, contact, abs(impulse_magnitude))
        return True

    def _teleport_fallback(self, ball: BallObject, state: RuntimeObjectState, portal: PortalObject) -> None:
        if self.time - self._portal_last_time.get(ball.id, -999.0) < portal.cooldown_ms / 1000.0:
            return
        target = self.models.get(portal.target_portal_id or "")
        if not isinstance(target, PortalObject):
            return
        velocity = self.velocities[ball.id]
        self._register_collision(
            ball, portal, state.position, math.hypot(*velocity) * max(0.001, ball.mass)
        )
        exit_direction = normalized(velocity, (1.0, 0.0))
        state.position = add(target.position, multiply(exit_direction, target.radius + ball.radius + 2.0))
        if not portal.preserve_velocity:
            velocity = (0.0, 0.0)
        else:
            velocity = multiply(velocity, portal.exit_speed_multiplier)
        self.velocities[ball.id] = velocity
        state.velocity = velocity
        self._portal_last_time[ball.id] = self.time
        event = PhysicsEvent(self.time, "portal", ball.id, portal.id, state.position, 0.0)
        self.physics_events.append(event)
        if self.event_callback:
            self.event_callback(event)

    def _update_kinematic_models(self, integration_dt: float) -> None:
        for model in list(self.models.values()):
            if isinstance(model, RingObject):
                state = self.states.get(model.id)
                if state is None:
                    continue
                state.rotation += model.rotation_speed * integration_dt
                model.rotation = state.rotation - model.opening_rotation
                model.radius += model.expand_rate * integration_dt
                if model.radius > model.maximum_radius:
                    model.radius = model.minimum_radius
                elif model.radius < model.minimum_radius:
                    model.radius = model.maximum_radius
                state.radius = model.radius
            elif isinstance(model, PolygonObject):
                state = self.states.get(model.id)
                if state is None:
                    continue
                state.rotation += model.rotation_speed * integration_dt
                model.rotation = state.rotation

    def _resolve_world_boundaries(self, ball: BallObject, state: RuntimeObjectState) -> None:
        if self.project.scene.physics.wraparound:
            width, height = self.project.scene.logical_width, self.project.scene.logical_height
            state.position = (state.position[0] % width, state.position[1] % height)
            return
        if not self.project.scene.physics.world_boundaries:
            return
        width, height = self.project.scene.logical_width, self.project.scene.logical_height
        x, y = state.position
        vx, vy = self.velocities[ball.id]
        contacts: list[tuple[str, tuple[float, float], tuple[float, float]]] = []
        if x - ball.radius < 0.0:
            x = ball.radius
            if vx < 0.0:
                vx = -vx * ball.restitution
            contacts.append(("world_left", (x, y), (1.0, 0.0)))
        elif x + ball.radius > width:
            x = width - ball.radius
            if vx > 0.0:
                vx = -vx * ball.restitution
            contacts.append(("world_right", (x, y), (-1.0, 0.0)))
        if y - ball.radius < 0.0:
            y = ball.radius
            if vy < 0.0:
                vy = -vy * ball.restitution
            contacts.append(("world_top", (x, y), (0.0, 1.0)))
        elif y + ball.radius > height:
            y = height - ball.radius
            if vy > 0.0:
                vy = -vy * ball.restitution
            contacts.append(("world_bottom", (x, y), (0.0, -1.0)))
        if contacts:
            state.position = (x, y)
            self.velocities[ball.id] = (vx, vy)
            state.velocity = (vx, vy)

            self._register_collision(ball, None, contacts[0][1], math.hypot(vx, vy) * ball.mass)

    def step(self, dt: float | None = None) -> SimulationSnapshot:
        step_dt = self.fixed_dt if dt is None else dt
        previous_time = self.time
        self._update_emitters(step_dt)
        settings = self.project.scene.physics
        substeps = self._effective_substeps(step_dt)
        integration_dt = step_dt * settings.simulation_speed / substeps
        gx, gy = settings.gravity

        for _ in range(substeps):
            self._update_kinematic_models(integration_dt)
            ball_models = [model for model in list(self.models.values()) if isinstance(model, BallObject)]
            for ball in ball_models:
                state = self.states.get(ball.id)
                if state is None:
                    continue
                vx, vy = self.velocities[ball.id]
                vx += gx * ball.gravity_scale * integration_dt
                vy += gy * ball.gravity_scale * integration_dt
                damping = settings.air_resistance
                vx *= damping ** (integration_dt * settings.physics_hz)
                vy *= damping ** (integration_dt * settings.physics_hz)
                speed = math.hypot(vx, vy)
                limit = min(ball.maximum_speed, settings.maximum_speed)
                if speed > limit > 0.0:
                    vx, vy = vx / speed * limit, vy / speed * limit
                state.position = (state.position[0] + vx * integration_dt, state.position[1] + vy * integration_dt)
                self.velocities[ball.id] = (vx, vy)
                state.velocity = (vx, vy)
                self._resolve_world_boundaries(ball, state)

                for surface in list(self.models.values()):
                    if surface.id == ball.id or surface.id not in self.models:
                        continue
                    if isinstance(surface, WallObject):
                        self._resolve_segment_surface(
                            ball,
                            state,
                            surface,
                            surface.start,
                            surface.end,
                            max(0.5, surface.thickness / 2.0),
                            surface.restitution,
                            surface.friction,
                        )
                    elif isinstance(surface, RingObject):
                        self._resolve_ring(ball, state, surface)
                    elif isinstance(surface, BumperObject):
                        self._resolve_bumper(ball, state, surface)
                    elif isinstance(surface, PolygonObject):
                        self._resolve_polygon(ball, state, surface)
                    elif isinstance(surface, PortalObject):
                        if math.dist(state.position, surface.position) < ball.radius + surface.radius:
                            self._teleport_fallback(ball, state, surface)

            current_balls = [model for model in list(self.models.values()) if isinstance(model, BallObject)]
            for index, first in enumerate(current_balls):
                for second in current_balls[index + 1:]:
                    self._resolve_ball_pair(first, second)
            self._flush_pending_removals()

        self.time += step_dt
        self.frame += 1
        for object_id, model in list(self.models.items()):
            if not isinstance(model, BallObject):
                continue
            state = self.states.get(object_id)
            if state and model.trail_enabled:
                self.trails[object_id].append(state.position)
                state.trail = list(self.trails[object_id])
            if model.lifetime_seconds > 0 and self.time - self._spawn_times.get(object_id, 0.0) >= model.lifetime_seconds:
                self._remove_runtime_object(object_id)

        self._update_scheduled_duplications(previous_time, self.time)
        self._update_spatial_duplications()
        self._flush_pending_removals()
        self._timeline_notes(previous_time, self.time)
        self._update_effects(step_dt)
        return self.snapshot()
