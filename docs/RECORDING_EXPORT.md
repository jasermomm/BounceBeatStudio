# Recording and export

## Export modes

### Offline deterministic

Frames are generated one by one from simulation time. Rendering may be slower than real time, but no output frame is dropped. This is the recommended final-output mode.

### Real-time paced

The exporter attempts to match wall-clock time while still using generated frames. It is useful for quick previews but depends more on machine performance.

## Pipeline

1. Validate resolution, FPS, duration, path, codec, and disk space.
2. Reset a deterministic simulation engine.
3. Render each frame through the same Qt scene renderer used by preview.
4. Pipe raw BGRA frames to FFmpeg or save PNG frames.
5. Render captured note events to an exact-duration stereo WAV.
6. Mux audio and video.
7. Preserve a partial intermediate when cancellation settings request it.

Desktop screen capture is never used.

## Outputs

- MP4, MKV, MOV, or WebM video
- WAV audio-only export
- PNG/JPEG image sequence plus optional WAV
- video-only output
- transparent output with supported codec/container pairs

## Codec compatibility

- MP4: H.264, H.265, or AV1; AAC or MP3 audio
- WebM: VP9 or AV1; Opus audio
- MOV: H.264, H.265, AV1, or QTRLE; AAC, MP3, or PCM audio
- MKV: broad codec support, including FFV1

Transparent combinations:

- VP9 in WebM
- FFV1 in MKV
- QTRLE in MOV

Transparent MP4 is rejected before rendering.

## Hardware encoders

The encoder scanner can select NVIDIA NVENC, Intel Quick Sync, AMD AMF, or software fallback when FFmpeg reports support. Hardware availability depends on drivers and the FFmpeg build.

## Quality

CRF or codec quality controls trade file size for visual quality. A lower CRF usually means higher quality for software H.264/H.265. Optional bitrate settings are used where appropriate.

## Synchronization

Simulation time determines both frame timestamps and note-event timestamps. Audio is forced to the exact requested sample count. Muxing uses the requested duration and `-shortest` to avoid trailing mismatch.

## Cancellation

Cancellation closes the frame pipe safely. When preserve-partial is enabled, the temporary video is copied to a `.partial` file rather than deleted silently.

## Missing FFmpeg

The application remains usable. Video options requiring FFmpeg fail with a readable message, while WAV and image-sequence paths continue to work.
