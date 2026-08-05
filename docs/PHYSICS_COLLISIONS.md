# Physics and collisions

## Fixed timestep

Normal physics uses a fixed internal timestep derived from the configured physics rate. Rendering FPS is independent, so changing output from 30 to 60 FPS does not change the physical result.

Pymunk is the primary backend. A deterministic pure-Python fallback supports core operation and tests when the native wheel is unavailable.

## Collision reliability

Continuous-collision detection estimates the distance a fast ball or rotating obstacle can travel during one base step and adds bounded adaptive substeps. Collision skin, ring thickness, wall thickness, ball radius, obstacle tip speed, and maximum adaptive substeps affect tunneling protection.

Connected segment neighbors are used for rings and world boundaries to prevent cracks between adjacent segments. Rotating/expanding rings preserve their live transform when collision geometry is rebuilt.

## Supported contacts

- Ball with wall or world boundary
- Ball with closed or open ring
- Ball with rotating polygon
- Ball with bumper
- Ball with ball
- Ball with portal trigger
- Ball with trigger or disabled ring
- Ball with breakable wall, ring, or polygon

Contacts produce normalized physics events used by MIDI, particles, flashes, counters, duplication, and the timeline.

## Rings

The visible opening and physical opening use the same shared geometry conversion. The opening rotates with the ring. Solid arcs are generated from exact endpoints, and the wraparound join is connected for closed rings.

Ring segment resolution increases geometric smoothness at additional physics cost. Thickness affects both rendering and contact geometry.

## Breakable objects

Breakable objects compare impact strength against their threshold. Native Pymunk removals are deferred until the physics space is unlocked, preventing invalid mutation inside collision callbacks.

## Portals

Portal triggers detect entry by radius and move a ball to the paired exit. Cooldowns prevent immediate recursive teleportation. Velocity can be preserved and multiplied.

## Duplication safety

Creation and removal requested by collision callbacks are queued safely. Per-ball trigger-event limits, maximum generation, maximum duplicates, emitter limits, and the global maximum-ball count prevent uncontrolled exponential growth.

Batch respawns use deterministic sunflower placement and are clamped inside a target ring's usable radius. If only part of a requested batch fits under the global cap, the engine creates the allowed number and stops at the limit.

## Determinism

Random choices use project or object-specific seeded generators. A repeated render with the same application version, project, MIDI, settings, and seed should produce the same sequence and motion.
