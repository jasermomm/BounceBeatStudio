# Installation

## Requirements

- Python 3.11 or newer
- Windows 10/11, macOS, or a modern Linux desktop
- FFmpeg for encoded video export
- Optional FluidSynth and a General MIDI `.sf2` SoundFont

No paid API, account, cloud service, or permanent internet connection is required.

## Windows source installation

Open PowerShell in the repository folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe run.py
```

Use `python` instead of `py -3.11` when the Python Launcher is unavailable.

## macOS and Linux source installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
python run.py
```

Linux systems may require desktop audio packages for PipeWire, PulseAudio, or ALSA. Headless rendering uses `QT_QPA_PLATFORM=offscreen` when no display is available.

## FFmpeg

BounceBeat searches:

1. The custom location saved in Settings
2. The application directory
3. The system `PATH`

Windows installation with winget:

```powershell
winget install Gyan.FFmpeg
ffmpeg -version
```

A portable `ffmpeg.exe` and `ffprobe.exe` can be placed in `vendor/` before building. The PyInstaller specification bundles them automatically when present. Redistribution must comply with the license of the FFmpeg build you choose.

Without FFmpeg, editing, previewing, MIDI, fallback audio, WAV export, and PNG sequences remain available. Encoded video export is disabled with an explanatory error.

## FluidSynth and SoundFonts

The built-in synthesizer works immediately. For realistic General MIDI instruments:

1. Install FluidSynth or its command-line executable.
2. Optionally install the Python binding:

```bash
python -m pip install -e ".[fluidsynth]"
```

3. Obtain a legal `.sf2` SoundFont.
4. Open **Tools → Settings** and choose the SoundFont.

SoundFonts are not bundled because their licenses and sizes vary.

## Run commands

```bash
python run.py
bouncebeat
bouncebeat-render --help
python -m bouncebeat.render --help
```

## Verify the installation

```bash
python -m compileall -q src tests scripts run.py
python -m pytest
python scripts/validate_release.py
```

The strict release check requires real PySide6 and Pymunk backends:

```bash
python scripts/validate_release.py --require-native
```
