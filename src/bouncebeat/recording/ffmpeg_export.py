from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from bouncebeat.audio.offline import render_note_events_to_wav
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.simulation.engine import SimulationEngine
from bouncebeat.utilities.ffmpeg import FFmpegInfo, preferred_video_encoder
from bouncebeat.utilities.validation import frame_count, validate_duration, validate_fps, validate_resolution

logger = logging.getLogger("bouncebeat.recording")


class ExportCancelled(RuntimeError):
    pass


@dataclass(slots=True)
class RenderProgress:
    stage: str
    current_frame: int
    total_frames: int
    simulation_time: float
    percent: float
    encoding_speed: float
    output_size: int


@dataclass(slots=True)
class RenderResult:
    output_path: Path
    frame_count: int
    duration: float
    note_count: int
    cancelled: bool = False
    partial_path: Path | None = None


class FFmpegCommandBuilder:
    H264_ENCODERS = {"libx264", "h264_nvenc", "h264_qsv", "h264_amf"}
    H265_ENCODERS = {"libx265", "hevc_nvenc", "hevc_qsv", "hevc_amf"}
    AV1_ENCODERS = {"libsvtav1", "libaom-av1"}

    @staticmethod
    def compatibility_error(
        output_path: str | Path,
        encoder: str,
        transparent: bool = False,
        audio_codec: str = "aac",
        include_audio: bool = True,
    ) -> str:
        suffix = Path(output_path).suffix.lower()
        supported = {".mp4", ".mkv", ".mov", ".webm"}
        if suffix not in supported:
            return "Video output must use .mp4, .mkv, .mov, or .webm."
        h264 = FFmpegCommandBuilder.H264_ENCODERS
        h265 = FFmpegCommandBuilder.H265_ENCODERS
        av1 = FFmpegCommandBuilder.AV1_ENCODERS
        if suffix == ".webm" and encoder not in {"libvpx-vp9", *av1}:
            return "WebM requires VP9 or AV1 video. Choose VP9/AV1 or use MKV/MP4."
        if suffix == ".mp4" and encoder not in {*h264, *h265, *av1}:
            return "MP4 requires H.264, H.265, or AV1. Use MKV for FFV1 or WebM for VP9."
        if suffix == ".mov" and encoder not in {*h264, *h265, *av1, "qtrle"}:
            return "MOV requires H.264, H.265, AV1, or QTRLE."
        if transparent:
            allowed_alpha = {
                ".webm": {"libvpx-vp9"},
                ".mkv": {"libvpx-vp9", "ffv1"},
                ".mov": {"qtrle"},
                ".mp4": set(),
            }
            if encoder not in allowed_alpha[suffix]:
                return (
                    "That codec/container cannot preserve transparency. "
                    "Use VP9 WebM, FFV1 MKV, or QTRLE MOV."
                )
        if include_audio:
            if suffix == ".webm" and audio_codec != "libopus":


                if audio_codec not in {"aac", "mp3"}:
                    return "WebM audio must use Opus."
            if suffix == ".mp4" and audio_codec not in {"aac", "mp3"}:
                return "MP4 audio must use AAC or MP3. Choose MKV/MOV for PCM audio."
            if suffix == ".mov" and audio_codec not in {"aac", "mp3", "pcm_s16le"}:
                return "MOV audio must use AAC, MP3, or PCM."
        return ""

    @staticmethod
    def video_command(
        ffmpeg_path: str,
        width: int,
        height: int,
        fps: int,
        encoder: str,
        crf: int,
        bitrate: str,
        transparent: bool,
        output_path: str | Path,
    ) -> list[str]:
        command = [
            ffmpeg_path, "-hide_banner", "-loglevel", "warning", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s:v", f"{width}x{height}",
            "-r", str(fps), "-i", "pipe:0", "-an", "-c:v", encoder,
        ]
        if encoder in {"libx264", "libx265"}:
            command += ["-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p"]
        elif encoder in {"h264_nvenc", "hevc_nvenc"}:
            command += ["-preset", "p5", "-cq", str(crf), "-pix_fmt", "yuv420p"]
        elif encoder in {"h264_qsv", "hevc_qsv"}:
            command += ["-global_quality", str(crf), "-pix_fmt", "yuv420p"]
        elif encoder in {"h264_amf", "hevc_amf"}:
            command += [
                "-quality", "balanced", "-rc", "cqp",
                "-qp_i", str(crf), "-qp_p", str(crf), "-pix_fmt", "yuv420p",
            ]
        elif encoder == "libvpx-vp9":
            command += ["-crf", str(crf), "-b:v", bitrate or "0", "-pix_fmt", "yuva420p" if transparent else "yuv420p"]
        elif encoder in {"libsvtav1", "libaom-av1"}:
            command += ["-crf", str(crf), "-b:v", bitrate or "0", "-pix_fmt", "yuv420p"]
        elif encoder in {"ffv1", "qtrle"}:
            command += ["-pix_fmt", "bgra" if transparent else "bgr0"]
        elif bitrate:
            command += ["-b:v", bitrate]
        command.append(str(output_path))
        return command

    @staticmethod
    def mux_command(
        ffmpeg_path: str,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: str | Path,
        audio_codec: str,
        audio_bitrate: str,
        duration: float,
    ) -> list[str]:
        if Path(output_path).suffix.lower() == ".webm" and audio_codec in {"aac", "mp3"}:
            audio_codec = "libopus"
        command = [
            ffmpeg_path, "-hide_banner", "-loglevel", "warning", "-y",
            "-i", str(video_path), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", audio_codec,
        ]
        if audio_bitrate and audio_codec not in {"pcm_s16le", "flac"}:
            command += ["-b:a", audio_bitrate]
        command += ["-t", f"{duration:.6f}", "-shortest"]
        if Path(output_path).suffix.lower() in {".mp4", ".mov"}:
            command += ["-movflags", "+faststart"]
        command.append(str(output_path))
        return command


class OfflineExporter:
    def __init__(
        self,
        project: BounceBeatProject,
        ffmpeg: FFmpegInfo,
        *,
        progress_callback: Callable[[RenderProgress], None] | None = None,
        preview_callback: Callable[[object], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> None:
        self.project = project
        self.ffmpeg = ffmpeg
        self.progress_callback = progress_callback
        self.preview_callback = preview_callback
        self.cancel_callback = cancel_callback or (lambda: False)

    def _validate(self, width: int, height: int, fps: int, duration: float, output: Path) -> None:
        for result in (validate_resolution(width, height), validate_fps(fps), validate_duration(duration)):
            if not result.valid:
                raise ValueError(result.message)
        if not output.parent.exists():
            output.parent.mkdir(parents=True, exist_ok=True)
        if not os.access(output.parent, os.W_OK):
            raise PermissionError(f"Output folder is not writable: {output.parent}")
        required = width * height * 4 * min(frame_count(duration, fps), fps * 3)
        free = shutil.disk_usage(output.parent).free
        if free < required:
            raise OSError("There may not be enough free disk space for temporary render data.")

    @staticmethod
    def _image_bytes(image) -> bytes:
        pointer = image.constBits()
        try:
            return pointer.asstring(image.sizeInBytes())
        except AttributeError:
            return pointer.tobytes()

    def render(
        self,
        output_path: str | Path,
        *,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
        duration: float | None = None,
        codec: str | None = None,
        crf: int | None = None,
        no_audio: bool = False,
        transparent: bool | None = None,
        realtime: bool = False,
    ) -> RenderResult:
        output = Path(output_path)
        width = int(width or self.project.render.width)
        height = int(height or self.project.render.height)
        fps = int(fps or self.project.render.fps)
        duration = float(duration or self.project.recording.duration_seconds)
        crf = int(crf if crf is not None else self.project.recording.crf)
        transparent = self.project.render.transparent if transparent is None else transparent
        total = frame_count(duration, fps)
        self._validate(width, height, fps, duration, output)

        audio_only = self.project.recording.audio_only or output.suffix.lower() == ".wav"
        image_sequence = self.project.recording.image_sequence or output.suffix.lower() in {".png", ".jpg", ".jpeg"}
        include_audio = self.project.recording.include_audio and not no_audio and not self.project.recording.video_only
        engine = SimulationEngine(self.project)
        from bouncebeat.rendering.qt_renderer import SceneRenderer
        renderer = SceneRenderer()
        start_wall = time.perf_counter()

        with tempfile.TemporaryDirectory(prefix="bouncebeat-render-") as temp_name:
            temp_dir = Path(temp_name)
            audio_temp = temp_dir / "audio.wav"
            process: subprocess.Popen | None = None
            encoder = codec or preferred_video_encoder(self.ffmpeg, self.project.recording.video_codec)
            temporary_suffix = ".mov" if encoder == "qtrle" else ".webm" if encoder == "libvpx-vp9" else ".mkv"
            video_temp = temp_dir / f"video{temporary_suffix}"
            if not audio_only and not image_sequence:
                compatibility_error = FFmpegCommandBuilder.compatibility_error(
                    output, encoder, transparent, self.project.recording.audio_codec, include_audio
                )
                if compatibility_error:
                    raise ValueError(compatibility_error)

            if not audio_only and not image_sequence:
                if not self.ffmpeg.available:
                    raise RuntimeError("FFmpeg is required for video export. Set its path in Settings.")
                command = FFmpegCommandBuilder.video_command(
                    self.ffmpeg.path, width, height, fps, encoder, crf,
                    self.project.recording.bitrate, transparent, video_temp,
                )
                logger.info("Starting video encoder: %s", command)
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

            sequence_dir = output if output.suffix == "" else output.parent / f"{output.stem}_frames"
            if image_sequence:
                sequence_dir.mkdir(parents=True, exist_ok=True)

            try:
                for frame_index in range(total):
                    if self.cancel_callback():
                        raise ExportCancelled("Render cancelled by user.")
                    target_time = (frame_index + 1) / fps
                    while engine.time + engine.fixed_dt <= target_time + 1e-9:
                        engine.step()
                    snapshot = engine.snapshot()
                    image = None
                    if not audio_only:
                        image = renderer.render(
                            self.project, snapshot, engine.models, width, height,
                            transparent=transparent, show_grid=False, show_safe_area=False,
                            show_stats=self.project.render.show_fps,
                            actual_fps=fps,
                            recording_text="",
                        )
                        if image_sequence:
                            image.save(str(sequence_dir / f"frame_{frame_index:08d}.png"))
                        else:
                            if process is None or process.stdin is None:
                                raise RuntimeError("FFmpeg video pipe is unavailable.")
                            process.stdin.write(self._image_bytes(image))
                    if image is not None and self.preview_callback and (frame_index % max(1, fps // 10) == 0 or frame_index == total - 1):
                        self.preview_callback(image)
                    elapsed = max(0.001, time.perf_counter() - start_wall)
                    speed = ((frame_index + 1) / fps) / elapsed
                    size = video_temp.stat().st_size if video_temp.exists() else 0
                    if self.progress_callback:
                        self.progress_callback(RenderProgress(
                            "rendering", frame_index + 1, total, snapshot.time,
                            (frame_index + 1) / total * 100.0, speed, size,
                        ))
                    if realtime:
                        deadline = start_wall + (frame_index + 1) / fps
                        delay = deadline - time.perf_counter()
                        if delay > 0:
                            time.sleep(delay)
                if process and process.stdin:
                    process.stdin.close()
                    process.stdin = None
                    return_code = process.wait()
                    if return_code != 0:
                        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
                        raise RuntimeError(f"FFmpeg video encoding failed: {stderr[-2000:]}")
            except ExportCancelled:
                if process and process.stdin:
                    try:
                        process.stdin.close()
                        process.stdin = None
                    except OSError:
                        pass
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                partial = output.with_name(output.stem + f".partial{temporary_suffix}")
                if video_temp.exists() and self.project.recording.preserve_partial:
                    shutil.copy2(video_temp, partial)
                return RenderResult(output, 0, duration, len(engine.note_events), True, partial if partial.exists() else None)
            finally:
                if process and process.poll() is None:
                    process.kill()

            if include_audio or audio_only:
                if self.progress_callback:
                    self.progress_callback(RenderProgress("audio", total, total, duration, 96.0, 0.0, 0))
                render_note_events_to_wav(
                    engine.note_events, duration, audio_temp,
                    sample_rate=self.project.audio.sample_rate,
                    waveform=self.project.audio.fallback_waveform.value,
                    master_volume=self.project.audio.master_volume,
                    soundfont_path=self.project.audio.soundfont_path,
                )

            if audio_only:
                destination = output if output.suffix.lower() == ".wav" else output.with_suffix(".wav")
                shutil.copy2(audio_temp, destination)
                return RenderResult(destination, total, duration, len(engine.note_events))
            if image_sequence:
                if include_audio:
                    shutil.copy2(audio_temp, sequence_dir / "audio.wav")
                return RenderResult(sequence_dir, total, duration, len(engine.note_events))

            if include_audio:
                if self.progress_callback:
                    self.progress_callback(RenderProgress("muxing", total, total, duration, 98.0, 0.0, video_temp.stat().st_size))
                mux = FFmpegCommandBuilder.mux_command(
                    self.ffmpeg.path, video_temp, audio_temp, output,
                    self.project.recording.audio_codec, self.project.recording.audio_bitrate, duration,
                )
                result = subprocess.run(mux, capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg muxing failed: {result.stderr[-2000:]}")
            else:
                remux = [
                    self.ffmpeg.path, "-hide_banner", "-loglevel", "warning", "-y",
                    "-i", str(video_temp), "-map", "0:v:0", "-c:v", "copy", str(output),
                ]
                result = subprocess.run(remux, capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg finalization failed: {result.stderr[-2000:]}")
            if self.progress_callback:
                self.progress_callback(RenderProgress("complete", total, total, duration, 100.0, 0.0, output.stat().st_size))
            return RenderResult(output, total, duration, len(engine.note_events))
