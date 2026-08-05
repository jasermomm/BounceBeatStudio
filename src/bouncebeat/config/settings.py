from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings


@dataclass(slots=True)
class AppSettings:
    ffmpeg_path: str = ""
    soundfont_path: str = ""
    theme: str = "dark"
    autosave_enabled: bool = True
    autosave_seconds: int = 60
    master_volume: float = 0.8
    sample_rate: int = 48000
    buffer_size: int = 512
    audio_device: str = "default"
    latency_ms: int = 30


class SettingsStore:
    def __init__(self) -> None:
        self.qsettings = QSettings("BounceBeat", "BounceBeat Studio")

    def load(self) -> AppSettings:
        q = self.qsettings
        return AppSettings(
            ffmpeg_path=str(q.value("tools/ffmpeg_path", "")),
            soundfont_path=str(q.value("audio/soundfont_path", "")),
            theme=str(q.value("ui/theme", "dark")),
            autosave_enabled=q.value("project/autosave_enabled", True, bool),
            autosave_seconds=int(q.value("project/autosave_seconds", 60)),
            master_volume=float(q.value("audio/master_volume", 0.8)),
            sample_rate=int(q.value("audio/sample_rate", 48000)),
            buffer_size=int(q.value("audio/buffer_size", 512)),
            audio_device=str(q.value("audio/device", "default")),
            latency_ms=int(q.value("audio/latency_ms", 30)),
        )

    def save(self, settings: AppSettings) -> None:
        q = self.qsettings
        q.setValue("tools/ffmpeg_path", settings.ffmpeg_path)
        q.setValue("audio/soundfont_path", settings.soundfont_path)
        q.setValue("ui/theme", settings.theme)
        q.setValue("project/autosave_enabled", settings.autosave_enabled)
        q.setValue("project/autosave_seconds", settings.autosave_seconds)
        q.setValue("audio/master_volume", settings.master_volume)
        q.setValue("audio/sample_rate", settings.sample_rate)
        q.setValue("audio/buffer_size", settings.buffer_size)
        q.setValue("audio/device", settings.audio_device)
        q.setValue("audio/latency_ms", settings.latency_ms)
        q.sync()

    def recent_projects(self) -> list[str]:
        value = self.qsettings.value("recent/projects", [])
        return list(value) if isinstance(value, list) else [str(value)] if value else []

    def recent_midi(self) -> list[str]:
        value = self.qsettings.value("recent/midi", [])
        return list(value) if isinstance(value, list) else [str(value)] if value else []

    def add_recent_project(self, path: str) -> None:
        items = [path, *[item for item in self.recent_projects() if item != path]][:10]
        self.qsettings.setValue("recent/projects", items)

    def add_recent_midi(self, path: str) -> None:
        items = [path, *[item for item in self.recent_midi() if item != path]][:10]
        self.qsettings.setValue("recent/midi", items)
