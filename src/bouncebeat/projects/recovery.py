from __future__ import annotations

from pathlib import Path

from bouncebeat.models.project import BounceBeatProject
from bouncebeat.utilities.paths import autosave_path

from .serializer import load_project, save_project


def write_recovery(project: BounceBeatProject) -> Path:
    original_path = project.project_path
    original_embedded = project.embedded_midi
    try:
        return save_project(project, autosave_path(), embed_midi=False)
    finally:
        project.project_path = original_path
        project.embedded_midi = original_embedded


def recovery_available() -> bool:
    return autosave_path().is_file()


def load_recovery() -> BounceBeatProject:
    return load_project(autosave_path())


def clear_recovery() -> None:
    autosave_path().unlink(missing_ok=True)
