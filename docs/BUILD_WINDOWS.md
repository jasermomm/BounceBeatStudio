# Building Windows releases

## Automated builder

Double-click:

```text
BUILD_WINDOWS_EXE.bat
```

The script:

1. Locates Python 3.11 or newer.
2. Creates or repairs `.venv`.
3. Installs runtime, test, and build dependencies.
4. Verifies PySide6, Pymunk, MIDI, NumPy, and SoundFile imports.
5. Compiles source files.
6. Runs the complete test suite.
7. Runs strict native release validation.
8. Detects optional bundled FFmpeg tools.
9. Runs PyInstaller using `packaging/bouncebeat.spec`.
10. Creates a portable ZIP and dependency snapshot.

Options:

```text
--clean-venv
--skip-tests
--no-pause
```

Skipping tests is intended only for diagnosis, not public releases.

## Output

```text
dist/BounceBeat Studio/BounceBeat Studio.exe
dist/BounceBeat-Studio-<version>-Windows.zip
dist/build-requirements.txt
```

This is a one-folder build. The DLLs and assets beside the executable are required.

## Bundling FFmpeg

Place optional executables here before building:

```text
vendor/ffmpeg.exe
vendor/ffprobe.exe
```

The spec bundles them into the application directory. Check the distribution license of the selected FFmpeg build.

## Manual PyInstaller build

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,build]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\validate_release.py --require-native
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean packaging\bouncebeat.spec
```

## GitHub Actions

The repository includes CI tests and a manual Windows packaging workflow. The packaging workflow uploads the one-folder build as an artifact; it does not publish a release automatically.
