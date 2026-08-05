# GitHub repository audit — 1.5.4

## Correctness fixes

- Removed the stale `target_toggle` statement that crashed the Properties panel whenever a ring was selected.
- Added a source-wide unresolved-global check so dangling names are detected before packaging.
- Added model-binding validation for every object property shown by the inspector.
- Added project-property path validation for every editable project setting.
- Added native Qt tests that construct the complete inspector for every selectable object type.
- Added native Qt smoke coverage for the preview, hierarchy, timeline, MIDI inspector, render dialog, settings dialog, and welcome dialog.
- Extended strict release validation so the Windows builder checks all object inspectors and top-level editor widgets even when the ordinary test phase is skipped.

## Repository preparation

- Kept the setup-first README and complete user/developer documentation.
- Kept contribution, support, conduct, security, issue, pull-request, CI, dependency-review, Dependabot, and Windows packaging files.
- Kept one authoritative asset tree under `src/bouncebeat/assets/`.
- Removed generated caches, local environments, build outputs, logs, and machine-local files.
- Preserved the previously completed removal of the discarded MIDI-timed alternate-motion feature.

## Privacy and secret scan

The repository was scanned for personal names, email addresses, Windows user-profile paths, Unix home paths, container paths, temporary workspaces, AI-assistant traces, and common secret assignments.

No personal-data, path, or secret findings were found in source, documentation, presets, embedded project JSON, MIDI strings, icons, workflows, or configuration files.

## Validation

Local validation completed on Python 3.13:

- 99 tests collected
- 95 passed
- 4 conditionally skipped because PySide6 and the native Pymunk binary wheel are unavailable in this Linux validation container
- source compilation passed
- source-wide unresolved-global validation passed
- every inspector binding matched a real scene-model field
- every project-property path resolved on a default project
- all nine built-in presets completed extended finite-state simulation
- deterministic fallback physics passed
- collision-to-MIDI-to-stereo-WAV integration passed
- FFmpeg H.264 encoding and AAC muxing passed
- wheel `bouncebeat_studio-1.5.4-py3-none-any.whl` built successfully
- the wheel contained all nine presets, the embedded piano/bass demo, theme, and icons
- the installed wheel loaded all presets and completed project save/reopen outside the source tree
- Windows builder version lookup remained safe for project paths containing spaces
- Markdown relative-link validation passed
- GitHub YAML files parsed successfully
- source-comment and privacy scans passed

The Windows builder installs PySide6 and Pymunk, runs the full suite, and requires strict native validation of Pymunk, Qt rendering, every object inspector, and all top-level editor widgets before producing an EXE.
