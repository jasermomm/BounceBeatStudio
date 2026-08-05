from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
)

from bouncebeat.models.enums import ExportMode
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.recording.ffmpeg_export import FFmpegCommandBuilder, RenderProgress, RenderResult
from bouncebeat.recording.worker import RenderWorker
from bouncebeat.utilities.ffmpeg import FFmpegInfo
from bouncebeat.utilities.validation import validate_duration, validate_fps, validate_resolution

logger = logging.getLogger("bouncebeat.ui.render")


class RenderDialog(QDialog):
    def __init__(self, project: BounceBeatProject, ffmpeg: FFmpegInfo, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self.ffmpeg = ffmpeg
        self.worker: RenderWorker | None = None
        self.setWindowTitle("Record / Offline Render")
        self.resize(700, 680)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        output_row = QHBoxLayout()
        default_name = f"{project.name.replace(' ', '_')}.mp4"
        default_path = str(Path.home() / "Videos" / default_name)
        self.output = QLineEdit(project.recording.output_path or default_path)
        browse = QPushButton("Browse")
        output_row.addWidget(self.output, 1)
        output_row.addWidget(browse)
        form.addRow("Output", output_row)
        self.mode = QComboBox()
        self.mode.addItem("Offline deterministic render (recommended)", "offline")
        self.mode.addItem("Real-time recording", "realtime")
        form.addRow("Mode", self.mode)
        res_row = QHBoxLayout()
        self.width = QSpinBox(); self.width.setRange(64, 16384); self.width.setValue(project.render.width)
        self.height = QSpinBox(); self.height.setRange(64, 16384); self.height.setValue(project.render.height)
        self.width.setPrefix("W "); self.height.setPrefix("H ")
        res_row.addWidget(self.width); res_row.addWidget(self.height)
        form.addRow("Resolution", res_row)
        self.fps = QSpinBox(); self.fps.setRange(1, 240); self.fps.setValue(project.render.fps)
        form.addRow("FPS", self.fps)
        self.duration = QDoubleSpinBox(); self.duration.setRange(0.1, 86400); self.duration.setDecimals(2); self.duration.setValue(project.recording.duration_seconds)
        form.addRow("Duration seconds", self.duration)
        self.codec = QComboBox()
        candidates = [
            ("H.264 software", "libx264"), ("H.264 NVIDIA NVENC", "h264_nvenc"),
            ("H.264 Intel Quick Sync", "h264_qsv"), ("H.264 AMD AMF", "h264_amf"),
            ("H.265 software", "libx265"), ("H.265 NVIDIA NVENC", "hevc_nvenc"),
            ("VP9", "libvpx-vp9"), ("AV1 (SVT)", "libsvtav1"), ("Lossless FFV1", "ffv1"),
        ]
        for label, name in candidates:
            if not ffmpeg.available or name in ffmpeg.encoders or name == "libx264":
                self.codec.addItem(label, name)
        index = self.codec.findData(project.recording.video_codec)
        self.codec.setCurrentIndex(max(0, index))
        form.addRow("Video codec", self.codec)
        self.crf = QSpinBox(); self.crf.setRange(0, 51); self.crf.setValue(project.recording.crf)
        form.addRow("Quality / CRF", self.crf)
        self.video_bitrate = QLineEdit(project.recording.bitrate)
        self.video_bitrate.setPlaceholderText("Optional, e.g. 12M (leave blank for CRF)")
        form.addRow("Video bitrate", self.video_bitrate)
        self.include_audio = QCheckBox(); self.include_audio.setChecked(project.recording.include_audio)
        form.addRow("Include audio (off = video-only)", self.include_audio)
        self.audio_codec = QComboBox()
        for label, name in (("AAC", "aac"), ("Opus", "libopus"), ("PCM lossless", "pcm_s16le")):
            self.audio_codec.addItem(label, name)
        audio_index = self.audio_codec.findData(project.recording.audio_codec)
        self.audio_codec.setCurrentIndex(max(0, audio_index))
        form.addRow("Audio codec", self.audio_codec)
        self.audio_bitrate = QComboBox()
        for value in ("96k", "128k", "192k", "256k", "320k"):
            self.audio_bitrate.addItem(value, value)
        bitrate_index = self.audio_bitrate.findData(project.recording.audio_bitrate)
        self.audio_bitrate.setCurrentIndex(max(0, bitrate_index))
        form.addRow("Audio bitrate", self.audio_bitrate)
        self.transparent = QCheckBox(); self.transparent.setChecked(project.render.transparent)
        form.addRow("Transparent background", self.transparent)
        self.audio_only = QCheckBox(); self.audio_only.setChecked(project.recording.audio_only)
        form.addRow("Audio-only WAV", self.audio_only)
        self.image_sequence = QCheckBox(); self.image_sequence.setChecked(project.recording.image_sequence)
        form.addRow("PNG image sequence", self.image_sequence)
        layout.addLayout(form)
        status = "FFmpeg ready" if ffmpeg.available else "FFmpeg not found: video export is unavailable, but WAV export still works."
        self.ffmpeg_label = QLabel(status)
        self.ffmpeg_label.setStyleSheet("color:#34D399" if ffmpeg.available else "color:#FBBF24")
        self.ffmpeg_label.setWordWrap(True)
        layout.addWidget(self.ffmpeg_label)
        self.preview = QLabel("Render preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(180)
        self.preview.setStyleSheet("background:#050814; border:1px solid #2D3954;")
        layout.addWidget(self.preview)
        self.progress = QProgressBar(); self.progress.setRange(0, 1000)
        layout.addWidget(self.progress)
        self.detail = QLabel("Ready")
        layout.addWidget(self.detail)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start render")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.close_button = QPushButton("Close")
        buttons.addStretch(1); buttons.addWidget(self.start_button); buttons.addWidget(self.cancel_button); buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        browse.clicked.connect(self._browse)
        self.start_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._cancel)
        self.close_button.clicked.connect(self.reject)
        self.audio_only.toggled.connect(self._mode_changed)
        self.image_sequence.toggled.connect(self._mode_changed)
        self.include_audio.toggled.connect(self._mode_changed)
        self._mode_changed()

    def _browse(self) -> None:
        if self.audio_only.isChecked():
            name, _ = QFileDialog.getSaveFileName(self, "Export audio", self.output.text(), "WAV audio (*.wav)")
        elif self.image_sequence.isChecked():
            name = QFileDialog.getExistingDirectory(self, "Choose image-sequence folder", str(Path(self.output.text()).parent))
        else:
            name, _ = QFileDialog.getSaveFileName(
                self, "Export video", self.output.text(), "MP4 video (*.mp4);;MKV video (*.mkv);;MOV video (*.mov);;WebM video (*.webm)"
            )
        if name:
            self.output.setText(name)

    def _mode_changed(self) -> None:
        video = not self.audio_only.isChecked() and not self.image_sequence.isChecked()
        self.codec.setEnabled(video)
        self.crf.setEnabled(video)
        self.transparent.setEnabled(video or self.image_sequence.isChecked())
        self.include_audio.setEnabled(not self.audio_only.isChecked())
        self.audio_codec.setEnabled(self.include_audio.isChecked() and not self.audio_only.isChecked())
        self.audio_bitrate.setEnabled(self.include_audio.isChecked() and not self.audio_only.isChecked())

    def _validate(self) -> str | None:
        for result in (validate_resolution(self.width.value(), self.height.value()), validate_fps(self.fps.value()), validate_duration(self.duration.value())):
            if not result.valid:
                return result.message
        if not self.output.text().strip():
            return "Choose an output path."
        if not self.ffmpeg.available and not self.audio_only.isChecked() and not self.image_sequence.isChecked():
            return "FFmpeg is not available. Configure its path in Settings or export WAV/image sequence instead."
        if not self.audio_only.isChecked() and not self.image_sequence.isChecked():
            compatibility_error = FFmpegCommandBuilder.compatibility_error(
                self.output.text().strip(),
                str(self.codec.currentData()),
                self.transparent.isChecked(),
                str(self.audio_codec.currentData()),
                self.include_audio.isChecked(),
            )
            if compatibility_error:
                return compatibility_error
        return None

    def _start(self) -> None:
        error = self._validate()
        if error:
            QMessageBox.warning(self, "Cannot start render", error)
            return
        output = Path(self.output.text().strip())
        if output.exists() and not self.image_sequence.isChecked():
            answer = QMessageBox.question(self, "Overwrite file?", f"{output.name} already exists. Replace it?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.project.render.width = self.width.value()
        self.project.render.height = self.height.value()
        self.project.render.fps = self.fps.value()
        self.project.render.transparent = self.transparent.isChecked()
        self.project.recording.mode = ExportMode(self.mode.currentData())
        self.project.recording.output_path = str(output)
        self.project.recording.duration_seconds = self.duration.value()
        self.project.recording.video_codec = self.codec.currentData()
        self.project.recording.crf = self.crf.value()
        self.project.recording.bitrate = self.video_bitrate.text().strip()
        self.project.recording.include_audio = self.include_audio.isChecked()
        self.project.recording.video_only = not self.include_audio.isChecked() and not self.audio_only.isChecked()
        self.project.recording.audio_codec = str(self.audio_codec.currentData())
        self.project.recording.audio_bitrate = str(self.audio_bitrate.currentData())
        self.project.recording.audio_only = self.audio_only.isChecked()
        self.project.recording.image_sequence = self.image_sequence.isChecked()
        self.worker = RenderWorker(
            self.project,
            self.ffmpeg,
            str(output),
            overrides={
                "width": self.width.value(), "height": self.height.value(), "fps": self.fps.value(),
                "duration": self.duration.value(), "codec": self.codec.currentData(), "crf": self.crf.value(),
                "no_audio": not self.include_audio.isChecked(), "transparent": self.transparent.isChecked(),
                "realtime": self.mode.currentData() == "realtime",
            },
            parent=self,
        )
        self.worker.progress.connect(self._progress)
        self.worker.preview.connect(self._preview)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._worker_finished)
        self.start_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.worker.start()

    def _progress(self, progress: RenderProgress) -> None:
        self.progress.setValue(round(progress.percent * 10))
        self.detail.setText(
            f"{progress.stage.title()} • frame {progress.current_frame:,}/{progress.total_frames:,} • "
            f"simulation {progress.simulation_time:.2f}s • {progress.encoding_speed:.2f}× real time • "
            f"{progress.output_size / (1024 * 1024):.1f} MB"
        )

    def _preview(self, image) -> None:
        pixmap = QPixmap.fromImage(image)
        self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _completed(self, result: RenderResult) -> None:
        if result.cancelled:
            text = "Render cancelled."
            if result.partial_path:
                text += f" Partial video kept at:\n{result.partial_path}"
            QMessageBox.information(self, "Render cancelled", text)
        else:
            QMessageBox.information(
                self, "Render complete",
                f"Saved to:\n{result.output_path}\n\n{result.frame_count:,} frames, {result.note_count:,} note events."
            )
            self.detail.setText(f"Complete: {result.output_path}")

    def _failed(self, details: str) -> None:
        logger.error("Render failed:\n%s", details)
        readable = details.split("\n", 1)[0]
        QMessageBox.critical(self, "Render failed", readable + "\n\nDetails were written to the BounceBeat log file.")
        self.detail.setText("Failed: " + readable)

    def _worker_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.close_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.worker = None

    def _cancel(self) -> None:
        if not self.worker:
            return
        answer = QMessageBox.question(
            self, "Cancel render?",
            "Stop the render? A playable partial file will be kept when FFmpeg has produced one."
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.detail.setText("Cancelling after the current frame…")
            self.worker.cancel()
            self.cancel_button.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Render in progress", "Cancel the active render before closing this window.")
            event.ignore()
            return
        super().closeEvent(event)
