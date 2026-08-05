# Changelog

## 1.5.4 — 2026-08-05

- Fixed a ring-selection crash caused by a stale `target_toggle` reference left behind after removing the discarded MIDI-timed motion feature.
- Added native Qt coverage that constructs the complete properties panel for every selectable scene-object type.
- Added a source-wide unresolved-global regression test to catch dangling names before packaging.
- Revalidated all normal physics, collision-triggered MIDI, audio, rendering, project, preset, and Windows-build workflows.

## 1.5.3 — 2026-08-05

- Removed the experimental MIDI-timed motion mode, its planner backend, UI controls, presets, demo project, tests, documentation, and serialized scene fields.
- Projects created by earlier versions still open; obsolete fields are ignored and the scene runs with the standard fixed-timestep physics engine.
- Restored one simulation path for preview and offline export, reducing maintenance surface and preventing mode-specific behavior differences.
- Retained all collision-triggered MIDI, timeline-synchronized visualizer playback, chain-reaction respawning, ball appearance controls, recording, packaging, and GitHub project infrastructure.


## 1.5.2

- Fixed the native Qt ball-appearance regression test so it renders independent flat and glossy simulation models.
- Fixed Windows builder version detection when the extracted project folder contains spaces.
- Added regression coverage for the space-safe builder path.

## 1.5.1 — 2026-08-05

- Reorganized the project as a public GitHub-ready repository with a concise root README and complete user, architecture, build, testing, privacy, support, security, and contribution documentation.
- Added cross-version Linux CI, strict manual Windows packaging, dependency review, Dependabot, issue forms, and a pull-request checklist.
- Removed duplicate root assets, generated caches, placeholder screenshots, version-specific audit files, and machine-local artifacts.
- Scrubbed source and bundled assets for personal names, email addresses, local user paths, secrets, and development-environment traces.
- Removed nonfunctional source comments while preserving executable behavior, string data, and necessary documentation.
- Updated the demo-MIDI generator to write into the package-owned asset directory.


## 1.4.0 — 2026-08-05

- Added four per-ball appearance modes: **Flat 2D**, **Soft shaded**, **Glossy**, and **Neon**.
- Added independent reflection toggle, strength, size, normalized highlight offset, shading strength, outline toggle, outline color, width, and opacity. Appearance is visual-only, inherited by duplicates, serialized in projects, and shared by preview/export.
- Preserved the original glossy look for older projects while allowing a completely flat circle with Flat 2D + Reflections off.
- Fixed native Pymunk breakable-object removal so it is deferred until the locked physics step finishes.
- Fixed live preview master volume being applied twice, which previously made low-volume settings disproportionately quiet.
- Added reference-counted overlapping same-pitch notes for both live and offline FluidSynth playback, preventing an earlier note-off from cutting a newer overlapping note short.
- Conformed external SoundFont WAV renders to the exact requested sample count, sample rate, stereo layout, and duration for reliable long-render synchronization.
- Fixed per-ball MIDI channel overrides, per-surface channel overrides, surface MIDI trigger enable/disable, and portal collision note triggering.
- Fixed timeline-synchronized playback when one frame crosses multiple MIDI loop boundaries, and made Continue Position / Restart Track settings work during simulation resets.
- Preserved exact elapsed-time expansion for native rings and kept disabled rings rotating visually without physical contact.
- Added codec/container/audio compatibility validation before export, plus corrected AMD AMF quality arguments.
- Added `scripts/validate_release.py` and made the Windows builder run native Pymunk, PySide6 rendering, packaged-asset, preset, collision-to-MIDI/audio, and optional FFmpeg smoke checks before creating an EXE.
- Expanded the regression suite to **93 tests**, including appearance independence, all-preset stress simulation, collision-to-WAV integration, MIDI overlap lifetime, exact audio duration, native locked-space removal, channel routing, multi-loop timing, and export compatibility.

## 1.3.0 — 2026-08-05

- Added **Balls spawned per trigger**, configurable from 1 to 64 for each ball.
- Added true death-chain behavior: one wall death can create N replacements inside the selected ring, and each replacement inherits the same setting.
- Made `max_duplicates` count trigger events per source ball, so a value of 1 permits exactly one death event while still allowing a multi-ball replacement batch.
- Added deterministic sunflower placement for multi-ball batches, preventing every child from spawning at one overlapping point.
- Kept batch positions inside the selected ring's safe usable radius and preserved deterministic seeded output.
- Added hard batch clamping and global maximum-ball enforcement, including partial batches when only a few slots remain.
- Updated **Escape and Respawn** to demonstrate a three-way `1 → 3 → 9 → 27` chain by default.
- Added regression tests for configurable batch sizes, one-ball compatibility, deterministic placement, global caps, project migration, serialization, and repeated three-way chains.

## 1.2.0 — 2026-08-05

- Added an **Any Wall** duplication trigger covering explicit wall objects and optional world boundaries.
- Added configurable duplicate spawn locations: collision point, original ball position, selected object center, or custom coordinates.
- Added current, initial, and random-direction velocity sources for newly created balls.
- Added optional source removal so a wall hit can behave as a true respawn instead of leaving an escaped ball bouncing outside.
- Added safe deferred creation and removal for Pymunk collision callbacks and generation reset for indefinite respawn loops.
- Added the editable **Escape and Respawn** preset with four walls, a rotating opening ring, and a ball that reappears inside the ring after reaching an outer wall.
- Added regression tests for wall-only filtering, target-centered spawning, world boundaries, source removal, generation reset, and serialization.

## 1.1.0 — 2026-08-05

- Rebuilt ring collision geometry as one exact connected arc with Chipmunk/Pymunk segment neighbors, eliminating the wrap-around seam that could let balls phase through the bottom-right portion of rotating rings.
- Corrected the preview/export angle conversion so the visible ring opening and the physical opening rotate in the same direction and occupy the same location.
- Preserved live ring angle and angular velocity when expanding or shrinking rings rebuild their collision geometry.
- Added adaptive anti-tunneling substeps based on ball speed, obstacle tip speed, radius, and thickness, with project controls for continuous collision detection, maximum collision substeps, and collision skin.
- Connected world-boundary segment neighbors to remove corner cracks.
- Added complete fallback collisions for walls, rings, rotating polygons, bumpers, ball-to-ball contact, portals, trigger rings, disabled rings, breakable objects, thickness, and radius.
- Made bumper extra impulse functional in both the Pymunk and fallback backends.
- Made both balls receive collision visuals, MIDI triggers, and duplication behavior during ball-to-ball contact.
- Added editable ring collision-segment resolution and strengthened the Circular Escape, Expanding Rings, and Obstacle Course presets.
- Expanded the automated suite to 61 tests, including multi-angle rotating-ring seam stress tests and high-speed bottom-right arc regression coverage.
- Packaged themes, icons, presets, and demo assets inside the Python package and pointed PyInstaller at the package-owned copy, so wheel and EXE builds no longer depend on the checkout layout.

## 1.0.1 — 2026-08-05

- Added a root-level `BUILD_WINDOWS_EXE.bat` that detects Python 3.11+, creates or repairs `.venv`, installs runtime/build/test dependencies, runs tests, builds with PyInstaller, and produces a portable Windows ZIP.
- Fixed the legacy BAT build path so test dependencies are installed before `pytest`, and made it forward to the new builder.
- Separated editor magnification from the project camera, so mouse-wheel zoom no longer changes exported framing.
- Added Fit Entire Canvas, Fit Canvas Width, Actual Pixels, editor panning, and a visible view-percentage indicator.
- Increased default and built-in preset object sizes so balls, walls, rings, bumpers, portals, trails, and visualizer elements read clearly in portrait videos.
- Raised the initial editor inspection zoom to 160% while retaining one-click full-canvas fitting.

## 1.0.0 — 2026-08-05

- Initial complete BounceBeat Studio repository.
- Fixed-step Pymunk simulation with deterministic fallback, collision cooldowns, duplication safety, emitters, rings, obstacles, portals, trails, ripples, particles, camera modes, and reproducible seeds.
- PySide6 editor with scene hierarchy, live preview, property inspector, timeline, MIDI inspection, settings, welcome workflow, undo/redo, drag editing, presets, autosave, recovery, and project persistence.
- Multi-track MIDI sequencing and synchronized real-time/offline audio with FluidSynth/SoundFont support and a built-in synthesizer fallback.
- Direct FFmpeg frame encoding, synchronized WAV generation and muxing, real-time paced and offline rendering, image sequences, cancellation, partial-file preservation, encoder detection, and CLI rendering.
- Eight editable presets, embedded piano-and-bass demo project, Windows PyInstaller build scripts, documentation, CI configuration, and 35 automated tests.
