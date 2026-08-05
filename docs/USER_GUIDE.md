# User guide

## Interface layout

### Scene panel

The left panel lists scene objects in draw order. Use it to select, rename, hide, lock, reorder, group, duplicate, and delete objects. Context menus expose common editing actions.

### Preview

The center panel displays the shared scene renderer used by preview and export. You can select and drag unlocked objects in edit mode. Mouse-wheel zoom changes editor magnification only; it does not change the exported camera.

Preview controls include play/pause, stop, restart, single-frame stepping, recording, grid, safe-area guides, FPS, fit canvas, fit width, 1:1 pixels, pan, and fullscreen.

### Properties panel

The right panel changes the selected object or project. Controls are generated from the current selection and validated before being stored.

### Timeline

The bottom timeline shows MIDI notes, collisions, object creation/deletion, portals, recording range, and loop range. It supports zooming and horizontal scrolling.

## Basic workflow

1. Create a blank project or open a preset.
2. Import a `.mid` or `.midi` file.
3. Select playable tracks in the MIDI inspector.
4. Assign tracks globally, per ball, or per surface.
5. Edit scene geometry and physics.
6. Configure color, ball appearance, trails, particles, and camera.
7. Set output resolution, FPS, and duration.
8. Preview with Space.
9. Save the `.bouncebeat` project.
10. Use offline rendering for final output.

## Adding objects

Use **Scene → Add Object** or the Scene panel menu. Available types are Ball, Wall, Ring, Bumper, Rotating obstacle, Portal, Emitter, Text overlay, and Particle system.

## Editing objects

- Drag unlocked objects in the preview.
- Use numeric fields for precise position and geometry.
- Copy/paste and duplicate preserve object settings while generating new IDs.
- Grouping stores a shared group label.
- Draw order follows the Scene panel order.
- Hidden objects are not rendered; locked objects cannot be dragged.

## Ball appearance

Four appearance modes are available:

- **Flat 2D:** solid fill; disable reflections for a completely flat circle
- **Soft shaded:** restrained depth shading
- **Glossy:** shading plus a configurable highlight
- **Neon:** glow-oriented appearance

Reflections, highlight strength, highlight size, highlight offset, shading strength, outline color, outline opacity, and outline width are independent. Appearance is visual only and never changes collision radius or mass.

## Colors

Paste one or more colors into the palette field using hex, RGB, or RGBA input. Supported behavior includes single color, random palette, cycle, time/speed/pitch gradients, track/instrument mapping, collision strength, random RGB, bright, pastel, rainbow, inherited colors, and palette progression.

Randomized behavior uses stored seeds so repeated renders remain reproducible.

## Camera and framing

Camera modes are static, follow selected object, follow average ball position, and automatic zoom. Camera pan and zoom are project settings and therefore affect exports. Editor view zoom is separate.

Use logical scene coordinates to keep physics unchanged when output resolution changes. Common portrait, landscape, and square resolutions are available, and custom dimensions are accepted after validation.

## Respawn and chain reactions

For the rotating-ring workflow, select a ball and configure:

- Duplication trigger: **Any Wall**
- Spawn mode: **Selected Object Center**
- Spawn target: the ring
- Remove source after duplication: enabled
- Reset generation on respawn: enabled
- Trigger events per ball: 1
- Balls spawned per trigger: 1 to 64

A value of 1 creates ordinary respawn. A value of 3 creates `1 → 3 → 9 → 27` until the project maximum-ball limit is reached.

## Saving and recovery

Projects can embed MIDI or reference it externally. Autosave stores a recovery project in the platform application-data directory. Recent projects and MIDI paths are stored locally. Window layout and shortcuts are restored on the next launch.

## Final rendering

Use offline deterministic mode for final-quality output. It advances the simulation frame by frame and cannot drop output frames when rendering is slower than real time. Real-time mode is useful for quick capture-style previews.
