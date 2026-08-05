from __future__ import annotations

import pytest

from bouncebeat.utilities.colors import ColorParseError, parse_color, parse_color_list
from bouncebeat.utilities.validation import estimate_audio_samples, frame_count, validate_fps, validate_resolution


def test_color_parsing_supported_formats():
    assert parse_color("#FF4D6D").to_hex() == "#FF4D6D"
    assert parse_color("255, 77, 109").to_hex() == "#FF4D6D"
    assert parse_color("rgba(255, 77, 109, 128)").to_hex(True) == "#FF4D6D80"
    assert parse_color_list("#FF4D6D, #FFD166\n6, 214, 160") == ["#FF4D6D", "#FFD166", "#06D6A0"]


def test_invalid_color_raises_readable_error():
    with pytest.raises(ColorParseError, match="Unsupported color format"):
        parse_color("definitely-not-a-color")


def test_resolution_and_fps_validation():
    assert validate_resolution(1080, 1920).valid
    assert not validate_resolution(20, 1920).valid
    assert validate_fps(60).valid
    assert not validate_fps(500).valid


def test_audio_video_duration_calculations():
    assert frame_count(30, 60) == 1800
    assert estimate_audio_samples(30, 48_000) == 1_440_000
