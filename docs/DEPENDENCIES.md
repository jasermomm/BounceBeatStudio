# Dependencies and external tools

## Required Python packages

- **PySide6:** desktop interface, painting, multimedia output, settings, and signals
- **Pymunk:** native Chipmunk2D physics backend
- **Mido:** MIDI file parsing and message construction
- **PrettyMIDI:** MIDI ecosystem compatibility and metadata support
- **NumPy:** synthesis, frame test data, and audio processing
- **SoundFile:** WAV reading and writing
- **platformdirs:** operating-system-specific settings, cache, data, and log folders

Version ranges are defined in `pyproject.toml` and mirrored in `requirements.txt` for simple installation tools.

## Optional Python packages

- **pyFluidSynth:** live SoundFont playback through a local FluidSynth library
- **pytest and pytest-cov:** development testing
- **Ruff:** critical static checks
- **PyInstaller and Pillow:** Windows packaging
- **build:** wheel and source-distribution creation

## External executables

### FFmpeg

Used for video encoding, encoder discovery, audio/video muxing, and finalization. The application can use a system installation, a path selected in Settings, or optional binaries placed in `vendor/` before building.

### FluidSynth

Used for realistic SoundFont rendering when installed. The internal synthesizer remains available without it.

## Assets not bundled

- SoundFonts
- copyrighted commercial MIDI
- third-party FFmpeg binaries
- third-party presets or media

Contributors must confirm redistribution rights before adding external assets. Dependency licenses remain the responsibility of their respective projects and distributors.
