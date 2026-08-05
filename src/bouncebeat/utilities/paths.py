from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir, user_log_dir

APP_NAME = "BounceBeat Studio"
APP_AUTHOR = "BounceBeat"


def bundled_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[3]


def resource_path(*parts: str) -> Path:
    root_candidate = bundled_root().joinpath(*parts)
    if root_candidate.exists() or not parts or parts[0] != "assets":
        return root_candidate
    package_assets = Path(__file__).resolve().parents[1] / "assets"
    return package_assets.joinpath(*parts[1:])


def config_dir() -> Path:
    path = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = Path(user_cache_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = Path(user_log_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def autosave_path() -> Path:
    return data_dir() / "recovery.bouncebeat"


def normalize_path(path: str) -> str:
    return os.path.normpath(os.path.expandvars(os.path.expanduser(path)))
