from __future__ import annotations

import traceback

from PySide6.QtCore import QThread, Signal

from bouncebeat.models.project import BounceBeatProject
from bouncebeat.utilities.ffmpeg import FFmpegInfo

from .ffmpeg_export import OfflineExporter, RenderProgress, RenderResult


class RenderWorker(QThread):
    progress = Signal(object)
    preview = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        project: BounceBeatProject,
        ffmpeg: FFmpegInfo,
        output_path: str,
        overrides: dict[str, object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.ffmpeg = ffmpeg
        self.output_path = output_path
        self.overrides = overrides or {}
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            exporter = OfflineExporter(
                self.project,
                self.ffmpeg,
                progress_callback=self.progress.emit,
                preview_callback=self.preview.emit,
                cancel_callback=lambda: self._cancelled,
            )
            result: RenderResult = exporter.render(self.output_path, **self.overrides)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")
