# Architecture

## Goals

- Separate project data from GUI state
- Keep physics independent from output FPS
- Share rendering and export paths
- Preserve deterministic output
- Degrade gracefully when optional native tools are missing
- Keep background work away from direct widget mutation

## Data flow

```text
MIDI file → parser → track metadata and notes → sequencer
Project model → fixed-timestep simulation backend → snapshots and events
Snapshots → Qt scene renderer → preview or encoded frames
Note events → live audio backend or offline WAV renderer
Frames + WAV → FFmpeg → final output
```

## Modules

### `models`

Dataclasses and enums for projects, scene objects, MIDI, recording, camera, and timeline. Serialization is explicit and versioned. Unknown fields from newer or older project files are ignored when safe defaults are available.

### `midi`

MIDI inspection, General MIDI metadata, track filtering, chord grouping, transformations, collision-controlled sequencing, and timeline-synchronized playback.

### `simulation`

`SimulationEngine` selects native Pymunk when available and otherwise uses the deterministic fallback backend. Both use project-defined fixed timesteps, collision cooldowns, population limits, event generation, and shared runtime snapshots. The native backend is intended for production; the fallback keeps tests and degraded operation available.

### `rendering`

The Qt renderer draws the complete scene into a `QImage`. Preview and offline export call the same renderer with different dimensions and overlay options.

### `audio`

Live audio is isolated from the UI. The built-in synthesizer and FluidSynth backend consume note events. Offline audio converts captured note events into an exact-duration WAV.

### `recording`

The exporter validates settings, advances the fixed-step simulation, renders frames, controls FFmpeg, renders audio, muxes, reports progress, and handles cancellation.

### `projects`

ZIP-based save/load, embedded assets, autosave, recent files, and recovery.

### `ui`

PySide6 windows, panels, dialogs, timeline, preview interaction, settings, and undo commands. Worker communication uses signals and callbacks rather than direct background-thread widget access.

### `utilities`

Color parsing, validation, platform paths, FFmpeg discovery, and logging.

## Determinism

A project stores its physics rate, seeds, MIDI state, initial object properties, and render settings. Normal simulation advances through fixed physics steps regardless of preview or output FPS. Random behavior uses project-owned seeded generators rather than uncontrolled module-level randomness.

Deterministic output still assumes the same application version, backend, assets, and settings. Native Pymunk and the fallback backend are each deterministic under their own supported conditions, but their contact details are not guaranteed to match each other exactly.

## Threading

The UI remains on the Qt main thread. Rendering and export work use worker objects and communicate through signals or callbacks. Background code does not directly mutate PySide widgets.

## Extension points

- Add scene object dataclasses and backend/render handlers
- Add MIDI mapping modes in the sequencer
- Add visual effects in snapshots and renderer
- Add codecs in command validation and builders
- Add presets as project data

Every extension should add serialization, UI, fallback/native behavior where applicable, documentation, and regression tests.
