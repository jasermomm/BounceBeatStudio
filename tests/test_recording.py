from __future__ import annotations

from pathlib import Path

from bouncebeat.recording.ffmpeg_export import FFmpegCommandBuilder
from bouncebeat.utilities.ffmpeg import FFmpegInfo, preferred_video_encoder


def test_ffmpeg_video_command_construction(tmp_path):
    output = tmp_path / "video.mkv"
    command = FFmpegCommandBuilder.video_command(
        "ffmpeg", 1080, 1920, 60, "libx264", 18, "", False, output
    )
    assert command[:4] == ["ffmpeg", "-hide_banner", "-loglevel", "warning"]
    assert ["-s:v", "1080x1920"] == command[command.index("-s:v"):command.index("-s:v") + 2]
    assert command[command.index("-r") + 1] == "60"
    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[-1] == str(output)


def test_webm_mux_uses_opus(tmp_path):
    command = FFmpegCommandBuilder.mux_command(
        "ffmpeg", "video.mkv", "audio.wav", tmp_path / "result.webm", "aac", "192k", 30
    )
    assert command[command.index("-c:a") + 1] == "libopus"
    assert command[command.index("-t") + 1] == "30.000000"


def test_hardware_encoder_preference():
    info = FFmpegInfo(available=True, encoders={"h264_qsv", "libx264"})
    assert preferred_video_encoder(info, "auto") == "h264_qsv"
    assert preferred_video_encoder(info, "libx264") == "libx264"


def test_transparent_codec_commands_choose_alpha_pixel_formats():
    vp9 = FFmpegCommandBuilder.video_command(
        "ffmpeg", 320, 240, 30, "libvpx-vp9", 20, "", True, "out.webm"
    )
    assert "yuva420p" in vp9
    qtrle = FFmpegCommandBuilder.video_command(
        "ffmpeg", 320, 240, 30, "qtrle", 0, "", True, "out.mov"
    )
    assert "bgra" in qtrle


def test_codec_container_compatibility_reports_invalid_combinations(tmp_path):
    assert FFmpegCommandBuilder.compatibility_error(
        tmp_path / "video.webm", "libx264"
    )
    assert FFmpegCommandBuilder.compatibility_error(
        tmp_path / "video.mp4", "libvpx-vp9"
    )
    assert FFmpegCommandBuilder.compatibility_error(
        tmp_path / "video.mp4", "libx264", transparent=True
    )
    assert FFmpegCommandBuilder.compatibility_error(
        tmp_path / "video.mp4", "libx264", audio_codec="pcm_s16le", include_audio=True
    )
    assert FFmpegCommandBuilder.compatibility_error(
        tmp_path / "video.webm", "libvpx-vp9", transparent=True,
        audio_codec="libopus", include_audio=True,
    ) == ""
    assert FFmpegCommandBuilder.compatibility_error(
        tmp_path / "video.mkv", "ffv1", transparent=True,
        audio_codec="pcm_s16le", include_audio=True,
    ) == ""


def test_amf_command_uses_amf_supported_quality_options(tmp_path):
    command = FFmpegCommandBuilder.video_command(
        "ffmpeg", 1920, 1080, 60, "h264_amf", 20, "", False, tmp_path / "out.mkv"
    )
    assert command[command.index("-quality") + 1] == "balanced"
    assert command[command.index("-rc") + 1] == "cqp"
    assert "-global_quality" not in command
