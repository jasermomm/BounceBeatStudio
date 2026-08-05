# Development

## Environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev,build]"
```

Windows activation is optional when commands call `.venv\Scripts\python.exe` directly.

## Common commands

```bash
python run.py
python -m pytest
python -m compileall -q src tests scripts run.py
ruff check src tests scripts run.py
ruff format --check src tests scripts run.py
python scripts/validate_release.py
python -m build
```

Install `build` separately when creating wheels:

```bash
python -m pip install build
```

## Repository layout

```text
src/bouncebeat/        application package and packaged assets
tests/                 regression and integration tests
scripts/               build, demo, and release validation tools
packaging/             PyInstaller specification
docs/                  user and developer documentation
.github/                CI, issue templates, and pull-request template
vendor/                 optional local FFmpeg binaries, ignored by Git
```

## Coding expectations

- Python 3.11+ syntax
- Dataclasses for persistent project state
- Fixed-timestep rules for normal physics
- Deterministic seeded randomness
- No direct Qt widget changes from workers
- Readable exceptions for user-facing failures
- Tests for serialization and both backend paths when relevant
- No paid APIs, telemetry, or hidden network dependencies

## Assets

Only package-owned assets under `src/bouncebeat/assets/` are authoritative. Do not add duplicate root asset trees. Confirm the license of third-party icons, SoundFonts, MIDI, FFmpeg binaries, and media before committing them.

## Pull requests

Keep changes focused. Update docs and `CHANGELOG.md` for user-visible behavior. Add a test that fails before the fix and passes afterward. Run the full suite and release validator before requesting review.
