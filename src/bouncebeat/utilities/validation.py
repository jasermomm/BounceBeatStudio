from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ValidationResult:
    valid: bool
    message: str = ""
    warning: str = ""


def validate_resolution(width: int, height: int) -> ValidationResult:
    if width < 64 or height < 64:
        return ValidationResult(False, "Width and height must be at least 64 pixels.")
    if width > 16384 or height > 16384:
        return ValidationResult(False, "The maximum supported dimension is 16384 pixels.")
    pixels = width * height
    if pixels > 33_177_600:
        return ValidationResult(True, warning="This resolution may require substantial memory and disk space.")
    return ValidationResult(True)


def validate_fps(fps: int) -> ValidationResult:
    if fps < 1:
        return ValidationResult(False, "FPS must be at least 1.")
    if fps > 240:
        return ValidationResult(False, "FPS above 240 is not supported.")
    if fps > 120:
        return ValidationResult(True, warning="Very high FPS can make rendering and encoding much slower.")
    return ValidationResult(True)


def validate_duration(duration: float) -> ValidationResult:
    if duration <= 0:
        return ValidationResult(False, "Duration must be greater than zero.")
    if duration > 24 * 60 * 60:
        return ValidationResult(False, "Duration cannot exceed 24 hours.")
    return ValidationResult(True)


def estimate_raw_frame_bytes(width: int, height: int, channels: int = 4) -> int:
    return int(width) * int(height) * int(channels)


def estimate_audio_samples(duration: float, sample_rate: int) -> int:
    return max(0, round(duration * sample_rate))


def frame_count(duration: float, fps: int) -> int:
    return max(1, round(duration * fps))
