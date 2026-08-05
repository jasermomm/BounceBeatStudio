# Troubleshooting

## Application does not start

Run from a terminal:

```bash
python run.py
```

Check the log folder through **Tools → Open Log Folder**. Recreate the environment when imports fail:

```powershell
BUILD_WINDOWS_EXE.bat --clean-venv
```

## PySide6 or Pymunk installation fails

Use a supported 64-bit Python version and upgrade pip. Avoid unsupported embedded Python distributions. Recreate `.venv` after changing Python versions.

## FFmpeg is missing

Install FFmpeg, place it beside the application, or select its path under Settings. Confirm `ffmpeg -version` works in a new terminal.

## No audio

- Press Audio Panic, then restart playback.
- Confirm master volume and audio device settings.
- Remove an invalid SoundFont path to force fallback synthesis.
- Increase buffer size or latency when audio crackles.
- Verify the MIDI track contains playable notes and is not muted.

## Notes retrigger too rapidly

Increase the global or per-ball collision cooldown. Sustained contacts should not use a zero cooldown unless repeated triggering is intentional.

## Ball passes through a surface

- Keep continuous-collision detection enabled.
- Increase maximum collision substeps.
- Increase wall/ring thickness or collision skin.
- Avoid extremely small balls at extreme speed.
- Increase ring segment count when a very large ring appears faceted.

## Ring opening looks misaligned

Use the latest project version and reset the simulation. Preview and physics use shared angle conversion; old exported videos are not modified retroactively.

## Duplication becomes too expensive

Lower balls spawned per trigger, maximum generation, emitter maximum, global maximum balls, particles, trails, or preview scale. The engine will not exceed the global ball cap.


## Hardware encoding fails

Choose software H.264 (`libx264`) or another encoder reported by FFmpeg. Hardware encoding requires compatible drivers and an FFmpeg build containing that encoder.

## Moved project cannot find MIDI

Reimport the MIDI and save with embedding enabled. Embedded demo projects do not depend on external paths.

## Transparent export fails

Use VP9 WebM, FFV1 MKV, or QTRLE MOV. H.264/H.265 MP4 transparency is intentionally rejected.
