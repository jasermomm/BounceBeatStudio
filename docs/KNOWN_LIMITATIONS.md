# Known limitations

- BounceBeat Studio is a creative animation tool, not a full MIDI editor or digital audio workstation. It focuses on notes, timing, programs, tracks, mute/solo, volume, and pan rather than complete controller automation.
- The deterministic fallback physics backend is designed for graceful operation and tests, but native Pymunk is the intended production backend and may not produce identical contact details to the fallback.
- SoundFont quality depends on the external `.sf2` file and FluidSynth installation. No SoundFont is bundled.
- Hardware video encoders depend on operating-system drivers and the selected FFmpeg build.
- Very high resolutions, FPS values, glow, long trails, large particle counts, and thousands of balls can exceed available CPU, GPU, memory, or disk bandwidth.
- Preview speed can drop without affecting offline frame correctness. Offline export may be substantially slower than real time.
- Transparent output is limited to VP9 WebM, FFV1 MKV, and QTRLE MOV in the current exporter.
- The PyInstaller output is a one-folder application. The executable cannot be distributed alone without its adjacent libraries and assets.
- Project format migration currently relies on compatible defaults and ignored unknown keys. A formal multi-version migration registry can be added if the format changes substantially.
