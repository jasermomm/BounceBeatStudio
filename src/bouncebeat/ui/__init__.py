"""Desktop user interface, imported lazily."""
from __future__ import annotations

from typing import Any

__all__ = ["MainWindow"]


def __getattr__(name: str) -> Any:
    if name == "MainWindow":
        from .main_window import MainWindow

        return MainWindow
    raise AttributeError(name)
