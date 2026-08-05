from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .paths import bundled_root, normalize_path


@dataclass(slots=True)
class FFmpegInfo:
    path: str = ""
    available: bool = False
    version: str = ""
    encoders: set[str] = field(default_factory=set)
    error: str = ""

    def supports(self, encoder: str) -> bool:
        return encoder in self.encoders


def detect_ffmpeg(saved_path: str = "") -> FFmpegInfo:
    candidates: list[str] = []
    if saved_path:
        candidates.append(normalize_path(saved_path))
    executable = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    candidates.append(str(bundled_root() / executable))
    path_match = shutil.which("ffmpeg")
    if path_match:
        candidates.append(path_match)

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if not Path(candidate).is_file():
            continue
        try:
            version_result = subprocess.run(
                [candidate, "-hide_banner", "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if version_result.returncode != 0:
                continue
            first_line = (version_result.stdout or version_result.stderr).splitlines()[0]
            encoders_result = subprocess.run(
                [candidate, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            encoders: set[str] = set()
            for line in encoders_result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] in "VAS":
                    encoders.add(parts[1])
            return FFmpegInfo(
                path=candidate,
                available=True,
                version=first_line,
                encoders=encoders,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            last_error = str(exc)
    return FFmpegInfo(error=locals().get("last_error", "FFmpeg was not found."))


def preferred_video_encoder(info: FFmpegInfo, requested: str = "auto") -> str:
    if requested and requested != "auto" and info.supports(requested):
        return requested
    for encoder in ("h264_nvenc", "h264_qsv", "h264_amf", "libx264"):
        if info.supports(encoder):
            return encoder
    return "libx264"
