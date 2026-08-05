from __future__ import annotations

import colorsys
import random
import re
from dataclasses import dataclass

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB_FUNC_RE = re.compile(r"^rgba?\(([^)]+)\)$", re.IGNORECASE)


class ColorParseError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class RGBA:
    r: int
    g: int
    b: int
    a: int = 255

    def to_hex(self, include_alpha: bool = False) -> str:
        if include_alpha or self.a != 255:
            return f"#{self.r:02X}{self.g:02X}{self.b:02X}{self.a:02X}"
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"


def _channel(value: str) -> int:
    try:
        number = int(float(value.strip()))
    except ValueError as exc:
        raise ColorParseError(f"Invalid color channel: {value!r}") from exc
    if not 0 <= number <= 255:
        raise ColorParseError("RGB and alpha channels must be between 0 and 255.")
    return number


def parse_color(value: str) -> RGBA:
    text = value.strip()
    match = _HEX_RE.fullmatch(text)
    if match:
        raw = match.group(1)
        if len(raw) == 6:
            raw += "FF"
        return RGBA(*(int(raw[index:index + 2], 16) for index in range(0, 8, 2)))

    func_match = _RGB_FUNC_RE.fullmatch(text)
    if func_match:
        parts = [part.strip() for part in func_match.group(1).split(",")]
        if len(parts) not in (3, 4):
            raise ColorParseError("rgb() requires 3 channels and rgba() requires 4.")
        channels = [_channel(part) for part in parts]
        if len(channels) == 3:
            channels.append(255)
        return RGBA(*channels)

    parts = [part.strip() for part in text.split(",")]
    if len(parts) in (3, 4) and all(part for part in parts):
        channels = [_channel(part) for part in parts]
        if len(channels) == 3:
            channels.append(255)
        return RGBA(*channels)

    raise ColorParseError(f"Unsupported color format: {value!r}")


def parse_color_list(text: str) -> list[str]:
    colors: list[str] = []
    for raw_line in text.replace(";", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        numeric_parts = [part.strip() for part in line.split(",")]
        if len(numeric_parts) in (3, 4) and all(re.fullmatch(r"\d+(?:\.\d+)?", p) for p in numeric_parts):
            colors.append(parse_color(line).to_hex(include_alpha=len(numeric_parts) == 4))
            continue
        tokens = [token.strip() for token in line.split(",") if token.strip()]
        for token in tokens:
            colors.append(parse_color(token).to_hex(include_alpha=len(token.lstrip("#")) == 8))
    if not colors:
        raise ColorParseError("Enter at least one valid color.")
    return colors


def interpolate_color(a: str, b: str, amount: float) -> str:
    left, right = parse_color(a), parse_color(b)
    t = max(0.0, min(1.0, amount))
    return RGBA(
        round(left.r + (right.r - left.r) * t),
        round(left.g + (right.g - left.g) * t),
        round(left.b + (right.b - left.b) * t),
        round(left.a + (right.a - left.a) * t),
    ).to_hex(include_alpha=left.a != 255 or right.a != 255)


def random_color(mode: str, rng: random.Random) -> str:
    if mode == "pastel":
        h = rng.random()
        s = rng.uniform(0.3, 0.6)
        v = rng.uniform(0.85, 1.0)
    elif mode == "bright":
        h = rng.random()
        s = rng.uniform(0.75, 1.0)
        v = rng.uniform(0.85, 1.0)
    else:
        return RGBA(rng.randrange(256), rng.randrange(256), rng.randrange(256)).to_hex()
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return RGBA(round(r * 255), round(g * 255), round(b * 255)).to_hex()


def rainbow_color(angle: float, saturation: float = 0.9, lightness: float = 0.58) -> str:
    r, g, b = colorsys.hls_to_rgb((angle % 360.0) / 360.0, lightness, saturation)
    return RGBA(round(r * 255), round(g * 255), round(b * 255)).to_hex()
