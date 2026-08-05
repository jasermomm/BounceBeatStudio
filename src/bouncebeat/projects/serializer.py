from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from bouncebeat.models.project import BounceBeatProject


class ProjectFormatError(ValueError):
    pass


def _safe_member(name: str) -> bool:
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts


def save_project(project: BounceBeatProject, path: str | Path, embed_midi: bool | None = None) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".bouncebeat":
        target = target.with_suffix(".bouncebeat")
    target.parent.mkdir(parents=True, exist_ok=True)
    embed = project.embedded_midi if embed_midi is None else embed_midi
    project.touch()
    data = project.to_dict()
    data["embedded_midi"] = bool(embed)
    midi_path = Path(project.midi_asset.path) if project.midi_asset.path else None
    if midi_path and midi_path.is_file():
        if embed:
            asset_name = f"assets/{midi_path.name}"
            data["midi_asset"]["path"] = asset_name
            data["midi_asset"]["embedded_name"] = midi_path.name
        else:
            try:
                data["midi_asset"]["path"] = os.path.relpath(midi_path, target.parent)
            except ValueError:
                data["midi_asset"]["path"] = str(midi_path)

    fd, temporary_name = tempfile.mkstemp(prefix=target.stem, suffix=".tmp", dir=target.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("project.json", json.dumps(data, indent=2, ensure_ascii=False))
            if embed and midi_path and midi_path.is_file():
                archive.write(midi_path, f"assets/{midi_path.name}")
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    project.project_path = str(target.resolve())
    project.embedded_midi = bool(embed)
    return target


def load_project(path: str | Path, extraction_dir: str | Path | None = None) -> BounceBeatProject:
    source = Path(path)
    if not source.is_file():
        raise ProjectFormatError(f"Project file does not exist: {source}")
    try:
        with zipfile.ZipFile(source, "r") as archive:
            if "project.json" not in archive.namelist():
                raise ProjectFormatError("This archive does not contain project.json.")
            if any(not _safe_member(name) for name in archive.namelist()):
                raise ProjectFormatError("The project contains an unsafe asset path.")
            raw = archive.read("project.json")
            data = json.loads(raw.decode("utf-8"))
            project = BounceBeatProject.from_dict(data)
            project.project_path = str(source.resolve())
            midi_ref = project.midi_asset.path
            if project.embedded_midi and midi_ref:
                destination_root = Path(extraction_dir) if extraction_dir else source.parent / f".{source.stem}_assets"
                destination_root.mkdir(parents=True, exist_ok=True)
                member = midi_ref.replace("\\", "/")
                if member in archive.namelist():
                    output = destination_root / Path(member).name
                    with archive.open(member) as incoming, output.open("wb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                    project.midi_asset.path = str(output.resolve())
            elif midi_ref and not Path(midi_ref).is_absolute():
                project.midi_asset.path = str((source.parent / midi_ref).resolve())
            return project
    except ProjectFormatError:
        raise
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, OSError, KeyError, TypeError) as exc:
        raise ProjectFormatError(f"Could not open project: {exc}") from exc
