"""Audio backends.

Qt is imported lazily so the offline synthesizer and test suite can run in
headless environments that do not have PySide6 installed.
"""
from __future__ import annotations

from typing import Any

__all__ = ["AudioEngine", "render_note_events_to_wav"]


def __getattr__(name: str) -> Any:
    if name == "AudioEngine":
        from .engine import AudioEngine

        return AudioEngine
    if name == "render_note_events_to_wav":
        from .offline import render_note_events_to_wav

        return render_note_events_to_wav
    raise AttributeError(name)
