# Release checklist

## Repository

- [ ] Version updated in `pyproject.toml`, `src/bouncebeat/__init__.py`, and `CHANGELOG.md`
- [ ] No generated caches, environments, builds, logs, media exports, or local settings committed
- [ ] Personal-data and secret scan clean
- [ ] Packaged assets exist only under `src/bouncebeat/assets/`
- [ ] README and affected documentation updated
- [ ] License and third-party asset rights reviewed

## Automated validation

```bash
python -m compileall -q src tests scripts run.py
ruff check src tests scripts run.py
ruff format --check src tests scripts run.py
python -m pytest
python scripts/validate_release.py --require-native
```

- [ ] Wheel builds and installs in a clean environment
- [ ] PyInstaller one-folder build succeeds on Windows
- [ ] Application starts from the built folder

## Manual workflows

- [ ] Import MIDI containing piano and bass
- [ ] Verify both tracks and instruments appear
- [ ] Assign tracks to separate balls
- [ ] Preview synchronized collision-triggered notes
- [ ] Verify flat and glossy ball appearance modes
- [ ] Test closed and rotating-open ring collisions at several angles
- [ ] Test Any Wall respawn with spawn count 1
- [ ] Test chain reaction `1 → 3 → 9`
- [ ] Save, close, reopen, and compare settings
- [ ] Render a 1080×1920 60 FPS MP4 with audio
- [ ] Play the exported file and confirm duration and synchronization
- [ ] Cancel a render and confirm partial-file behavior
- [ ] Run Audio Panic and verify active notes stop

## Publication

- [ ] Create a signed or annotated version tag
- [ ] Attach source archive and Windows portable ZIP
- [ ] Publish checksums
- [ ] Summarize user-visible changes and known limitations
