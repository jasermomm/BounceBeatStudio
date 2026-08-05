# Contributing

Contributions are welcome through focused issues and pull requests.

## Before changing code

1. Search existing issues.
2. Describe the bug or feature and its expected behavior.
3. Keep the change limited to one clear purpose.
4. Avoid adding paid services, telemetry, or non-redistributable assets.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,build]"
```

On Windows, call `.venv\Scripts\python.exe` directly or activate the environment.

## Required checks

```bash
python -m compileall -q src tests scripts run.py
ruff check src tests scripts run.py
ruff format --check src tests scripts run.py
python -m pytest
python scripts/validate_release.py
```

Changes to native collision or Qt rendering should also pass:

```bash
python scripts/validate_release.py --require-native
```

## Pull requests

- Add regression tests for bug fixes.
- Update documentation for user-visible changes.
- Add a changelog entry.
- Do not commit `.venv`, builds, exports, logs, SoundFonts, copyrighted MIDI, or local FFmpeg binaries.
- Preserve deterministic output and fixed-timestep behavior.
- Do not mutate PySide widgets directly from worker threads.

By contributing, you agree that your contribution is licensed under the repository's MIT License.
