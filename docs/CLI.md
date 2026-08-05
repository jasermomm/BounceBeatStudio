# Command-line renderer

Render a saved project without opening the editor:

```bash
python -m bouncebeat.render project.bouncebeat --output video.mp4
```

Installed command:

```bash
bouncebeat-render project.bouncebeat --output video.mp4
```

## Options

```text
--width INTEGER
--height INTEGER
--fps INTEGER
--duration FLOAT
--codec NAME
--quality INTEGER
--seed INTEGER
--no-audio
--transparent
--ffmpeg PATH
--realtime
```

Examples:

```bash
bouncebeat-render scene.bouncebeat --output final.mp4 --width 1080 --height 1920 --fps 60 --duration 30
bouncebeat-render scene.bouncebeat --output transparent.webm --codec libvpx-vp9 --transparent
bouncebeat-render scene.bouncebeat --output audio.wav
bouncebeat-render scene.bouncebeat --output frames.png --no-audio
```

The renderer uses the same project loader, simulation engine, Qt renderer, note-event capture, audio renderer, and FFmpeg command builder as the GUI.

On a headless Linux system, the command automatically selects the Qt offscreen platform when `DISPLAY` is not set.
