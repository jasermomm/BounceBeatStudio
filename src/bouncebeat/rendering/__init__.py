"""Qt rendering components, imported lazily for headless core usage."""
from __future__ import annotations

from typing import Any

__all__ = ["SceneRenderer"]


def __getattr__(name: str) -> Any:
    if name == "SceneRenderer":
        from .qt_renderer import SceneRenderer

        return SceneRenderer
    raise AttributeError(name)
