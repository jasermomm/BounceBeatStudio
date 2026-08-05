# BounceBeat Studio

BounceBeat Studio is a desktop editor for creating musical 2D physics videos. Import MIDI, assign tracks to balls or surfaces, build a scene, preview it in real time, and export synchronized video and audio without screen recording.

## Highlights

- Fixed-timestep Pymunk physics with deterministic seeds
- MIDI track inspection, multi-track assignment, chords, mute, solo, transpose, tempo, and sequencing modes
- Balls, walls, rings, rotating openings, polygons, bumpers, portals, emitters, particles, trails, glow, and breakable objects
- Wall-triggered respawn and configurable chain-reaction multiplication
- Flat, shaded, glossy, and neon ball appearances with optional reflections and outlines
- Built-in synthesizer plus optional FluidSynth and SoundFont playback
- Direct FFmpeg export to video, audio, or image sequences
- Editable presets, project saving, autosave, recovery, undo/redo, and a headless renderer
- Windows EXE builder and automated release checks

## Quick setup

### Windows

1. Install 64-bit Python 3.11 or newer.
2. Extract or clone the repository.
3. Double-click `BUILD_WINDOWS_EXE.bat` to create the environment, run tests, validate native physics/rendering, and build the EXE.

To run from source instead:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe run.py
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python run.py
```

FFmpeg is required for encoded video export. FluidSynth and a `.sf2` SoundFont are optional because the application includes a fallback synthesizer.

## First project

1. Open **File → Import MIDI**.
2. Select one or more playable tracks.
3. Open a preset from **Scene → Presets**.
4. Select a ball and assign MIDI tracks in the Properties panel.
5. Adjust colors, physics, appearance, resolution, FPS, and recording duration.
6. Press Space to preview.
7. Open **Recording → Record / Render** for deterministic export.


## Demo projects

The package includes self-contained examples with embedded MIDI:

```text
src/bouncebeat/assets/demo/piano_bass_orchestra.bouncebeat
```

## Documentation

- [Documentation index](docs/README.md)
- [Installation](docs/INSTALLATION.md)
- [User guide](docs/USER_GUIDE.md)
- [Object and property reference](docs/OBJECT_REFERENCE.md)
- [MIDI and audio](docs/MIDI_AUDIO.md)
- [Physics and collisions](docs/PHYSICS_COLLISIONS.md)
- [Recording and export](docs/RECORDING_EXPORT.md)
- [Projects and presets](docs/PROJECTS_PRESETS.md)
- [Windows builds](docs/BUILD_WINDOWS.md)
- [Command-line renderer](docs/CLI.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development and testing](docs/DEVELOPMENT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Privacy](docs/PRIVACY.md)
- [Dependencies and external tools](docs/DEPENDENCIES.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)

## Tests

```bash
python -m pytest
python scripts/validate_release.py
```

The Windows builder runs the strict native validation command automatically:

```powershell
.\.venv\Scripts\python.exe scripts\validate_release.py --require-native
```

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Security reports should follow [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
