# Object and property reference

## Shared object properties

Every scene object has an ID, name, visibility, lock state, group, position, rotation, color, glow, MIDI-track list, optional MIDI channel override, MIDI-trigger switch, and draw-order index.

## Ball

### Physics

- Radius, mass, initial velocity, maximum speed
- Gravity scale, restitution, friction
- Rotation and angular velocity
- Per-ball collision cooldown
- Optional lifetime

### Appearance

- Flat, soft shaded, glossy, or neon style
- Reflections on/off
- Reflection strength, size, and offset
- Shading strength
- Outline on/off, color, opacity, and width
- Color mode and change-on-collision/note switches
- Trail on/off, length, thickness, and opacity
- Particle burst on/off and particle count

### MIDI

- Assigned tracks
- Channel override
- MIDI-trigger switch

### Duplication and respawn

Triggers include none, every collision, selected object, strength threshold, collision count, MIDI note, beat, region entry, leaving a ring, interval, and any wall.

Modes include exact clone, velocity variation, size variation, palette progression, different track, and next channel.

Spawn locations include collision point, original position, selected-object center, and custom coordinates. Velocity can use current, initial, or random direction. Batch count supports 1 to 64 children per trigger. Generation, trigger-event, and global ball limits protect performance.

## Wall

A wall is a segment with start/end points, thickness, restitution, and friction. It can be breakable above a configured strength. Explicit walls and optional world boundaries count as walls for the Any Wall trigger.

## Ring

A ring has center, radius, thickness, opening angle, opening rotation, rotation speed, expansion rate, minimum/maximum radius, collision mode, breakability, and segment resolution.

Collision modes:

- `solid`: normal physical contact
- `trigger`: produces events without a solid response
- `disabled`: visual only

Connected segment neighbors remove artificial seams. Ring rebuilding preserves live angle and angular velocity while expanding or shrinking.

## Polygon or rotating obstacle

A polygon stores local vertices, rotation speed, restitution, friction, and breakability. Rectangular bars are the default, but project data supports arbitrary vertex lists.

## Bumper

A bumper has radius, restitution, and extra impulse. The impulse is applied after the normal contact response.

## Portal

A portal has radius, target portal ID, preserve-velocity switch, exit-speed multiplier, and cooldown. Pair two portals by assigning each target to the other.

## Emitter

An emitter controls spawn area, interval, initial count, maximum count, radius range, speed range, direction range, lifetime range, enabled state, and deterministic seed.

## Text overlay

A text overlay stores text, font size, opacity, alignment, position, color, and glow.

## Particle system

A particle system has enabled state, maximum particle count, style, gravity, and drag. Runtime particles are pooled and clamped by both local and global limits.

## Project settings

### Physics

Gravity, air resistance, simulation speed, internal physics rate, base substeps, continuous-collision detection, adaptive substep limit, collision skin, solver iterations, global friction/restitution, maximum speed, world boundaries, wraparound, deterministic seed, maximum balls, and maximum particles.

### Rendering

Width, height, FPS, preview scale, background, transparency, overlay switches, and preview quality.

### Camera

Mode, pan, zoom, smoothing, follow target, shake intensity, and framing.

### Timeline

Start/end, loop range, zoom, and scroll position.
