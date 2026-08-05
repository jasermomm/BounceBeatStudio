# Testing

## Unit and integration tests

Run:

```bash
python -m pytest
```

The suite covers:

- MIDI parsing and playable-track extraction
- multi-track sequencing and chords
- deterministic random and round-robin behavior
- collision cooldowns
- walls, rings, openings, thickness, rotating geometry, bumpers, portals, breakables, and ball contacts
- high-speed anti-tunneling regressions
- respawn, chain reactions, placement, and global caps
- ball appearance serialization and visual/physics independence
- project save/load and compatibility defaults
- colors, resolution, FPS, and duration validation
- audio sample count and overlapping-note handling
- FFmpeg command construction and codec compatibility
- preset stress simulation
- packaged asset discovery

## Release validator

```bash
python scripts/validate_release.py
```

This runs all presets, checks finite state and ball limits, generates collision-triggered MIDI audio, optionally renders a Qt frame, and performs an FFmpeg encode/mux smoke test when FFmpeg is found.

Strict mode:

```bash
python scripts/validate_release.py --require-native
```

Strict mode fails unless real Pymunk and PySide6 rendering are active. The Windows builder uses strict mode.

## CI

GitHub Actions runs compilation, linting, tests, and release validation. A separate Windows workflow builds and uploads the PyInstaller artifact on manual dispatch or version tags.

## Manual acceptance

Before a release, complete the checklist in [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md), including the piano/bass workflow, rotating-ring collision test, chain-reaction test, and exported MP4 playback.

## UI integrity checks

The suite statically rejects unresolved global names and invalid inspector bindings. On systems with PySide6 installed, it also constructs the Properties panel for every selectable object type and smoke-tests every top-level editor widget and dialog. The strict Windows release validator repeats these checks before packaging.

