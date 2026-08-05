# Projects and presets

## `.bouncebeat` format

A project is a ZIP container. It normally contains:

```text
project.json
assets/<embedded MIDI file>
```

`project.json` stores scene objects, physics, palette, selected tracks, extracted MIDI notes, playback settings, audio, render, recording, camera, timeline, seeds, and metadata.

## Asset handling

MIDI can be referenced externally or embedded. Embedded MIDI makes a project portable. External paths are normalized and relative paths are preferred where possible.

Missing assets produce readable errors. Project loading does not execute code from the archive.

## Save behavior

- Save writes the current project.
- Save As chooses a new path.
- Autosave writes a recovery project to the platform data directory.
- Crash recovery is offered on the next launch when a recovery file exists.
- Recent projects and MIDI files are stored in local application settings.

## Presets

Nine editable presets are included:

1. Classic Bounce
2. Circular Escape
3. Escape and Respawn
4. Duplicate on Bounce
5. Multi-Instrument Orchestra
6. Expanding Rings
7. Color Explosion
8. Obstacle Course
9. Music Visualizer

Preset data is packaged under `src/bouncebeat/assets/presets/`. Opening a preset creates a normal editable project; it is not a fixed video.

## Demo projects

- `piano_bass_orchestra.bouncebeat`: embedded piano and bass tracks with separate balls

## Compatibility

New fields have defaults so older project files can load. Unknown keys are ignored by dataclass reconstruction. The format version and application version are stored for future migration work.

## Preset import/export

Preset export serializes scene and project settings into JSON. Import creates an editable project from that data. Do not use preset JSON for untrusted code execution; it is data only.
