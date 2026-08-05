from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QKeySequenceEdit,
)

from bouncebeat.config.settings import AppSettings
from bouncebeat.utilities.ffmpeg import detect_ffmpeg


DEFAULT_SHORTCUTS = {
    "play_pause": "Space",
    "restart": "R",
    "record": "Ctrl+R",
    "save": "Ctrl+S",
    "save_as": "Ctrl+Shift+S",
    "open": "Ctrl+O",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Y",
    "delete": "Delete",
    "duplicate": "Ctrl+D",
    "fullscreen": "F11",
    "step": "Right",
}


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, shortcuts: dict[str, str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.shortcuts = dict(DEFAULT_SHORTCUTS | (shortcuts or {}))
        self.setWindowTitle("BounceBeat Studio Settings")
        self.resize(620, 640)
        main = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search settings…")
        main.addWidget(self.search)

        tools = QGroupBox("External tools")
        tools_form = QFormLayout(tools)
        ff_row = QHBoxLayout()
        self.ffmpeg_path = QLineEdit(settings.ffmpeg_path)
        ff_browse = QPushButton("Browse")
        ff_detect = QPushButton("Detect")
        ff_row.addWidget(self.ffmpeg_path, 1)
        ff_row.addWidget(ff_browse)
        ff_row.addWidget(ff_detect)
        tools_form.addRow("FFmpeg", ff_row)
        self.ffmpeg_status = QLabel()
        self.ffmpeg_status.setWordWrap(True)
        tools_form.addRow("Status", self.ffmpeg_status)
        sf_row = QHBoxLayout()
        self.soundfont_path = QLineEdit(settings.soundfont_path)
        sf_browse = QPushButton("Browse")
        sf_row.addWidget(self.soundfont_path, 1)
        sf_row.addWidget(sf_browse)
        tools_form.addRow("SoundFont (.sf2)", sf_row)
        main.addWidget(tools)

        audio = QGroupBox("Audio")
        audio_form = QFormLayout(audio)
        self.master_volume = QDoubleSpinBox()
        self.master_volume.setRange(0, 1)
        self.master_volume.setSingleStep(0.05)
        self.master_volume.setValue(settings.master_volume)
        audio_form.addRow("Master volume", self.master_volume)
        self.sample_rate = QSpinBox()
        self.sample_rate.setRange(8000, 192000)
        self.sample_rate.setValue(settings.sample_rate)
        audio_form.addRow("Sample rate", self.sample_rate)
        self.buffer_size = QSpinBox()
        self.buffer_size.setRange(64, 8192)
        self.buffer_size.setValue(settings.buffer_size)
        audio_form.addRow("Buffer size", self.buffer_size)
        self.audio_device = QComboBox()
        self.audio_device.addItem("System default", "default")
        try:
            for device in QMediaDevices.audioOutputs():
                description = device.description()
                self.audio_device.addItem(description, description)
        except Exception:
            pass
        device_index = self.audio_device.findData(settings.audio_device)
        self.audio_device.setCurrentIndex(max(0, device_index))
        audio_form.addRow("Output device", self.audio_device)
        self.latency_ms = QSpinBox()
        self.latency_ms.setRange(5, 500)
        self.latency_ms.setValue(settings.latency_ms)
        self.latency_ms.setSuffix(" ms")
        audio_form.addRow("Target latency", self.latency_ms)
        main.addWidget(audio)

        project = QGroupBox("Projects")
        project_form = QFormLayout(project)
        self.autosave = QCheckBox()
        self.autosave.setChecked(settings.autosave_enabled)
        project_form.addRow("Enable autosave", self.autosave)
        self.autosave_seconds = QSpinBox()
        self.autosave_seconds.setRange(15, 3600)
        self.autosave_seconds.setValue(settings.autosave_seconds)
        project_form.addRow("Autosave interval", self.autosave_seconds)
        main.addWidget(project)

        shortcuts_group = QGroupBox("Keyboard shortcuts")
        shortcuts_form = QFormLayout(shortcuts_group)
        self.shortcut_edits: dict[str, QKeySequenceEdit] = {}
        for key, label in [
            ("play_pause", "Play / pause"), ("restart", "Restart"), ("record", "Start / stop recording"),
            ("save", "Save"), ("save_as", "Save as"), ("open", "Open"), ("undo", "Undo"),
            ("redo", "Redo"), ("delete", "Delete object"), ("duplicate", "Duplicate object"),
            ("fullscreen", "Fullscreen preview"), ("step", "Step one frame"),
        ]:
            edit = QKeySequenceEdit(QKeySequence(self.shortcuts[key]))
            shortcuts_form.addRow(label, edit)
            self.shortcut_edits[key] = edit
        main.addWidget(shortcuts_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main.addWidget(buttons)
        ff_browse.clicked.connect(self._browse_ffmpeg)
        ff_detect.clicked.connect(self._detect)
        sf_browse.clicked.connect(self._browse_soundfont)
        self.search.textChanged.connect(self._filter)
        self.groups = [tools, audio, project, shortcuts_group]
        self._detect()

    def _browse_ffmpeg(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Choose FFmpeg executable", self.ffmpeg_path.text())
        if name:
            self.ffmpeg_path.setText(name)
            self._detect()

    def _browse_soundfont(self) -> None:
        name, _ = QFileDialog.getOpenFileName(self, "Choose SoundFont", self.soundfont_path.text(), "SoundFonts (*.sf2)")
        if name:
            self.soundfont_path.setText(name)

    def _detect(self) -> None:
        info = detect_ffmpeg(self.ffmpeg_path.text())
        if info.available:
            self.ffmpeg_path.setText(info.path)
            self.ffmpeg_status.setText(f"Ready: {info.version}\n{len(info.encoders)} encoders detected")
            self.ffmpeg_status.setStyleSheet("color:#34D399")
        else:
            self.ffmpeg_status.setText("Not found. Preview and audio still work; video export will be disabled.")
            self.ffmpeg_status.setStyleSheet("color:#FBBF24")

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for group in self.groups:
            group.setVisible(not needle or needle in group.title().lower() or any(
                needle in label.text().lower() for label in group.findChildren(QLabel)
            ))

    def values(self) -> tuple[AppSettings, dict[str, str]]:
        settings = AppSettings(
            ffmpeg_path=self.ffmpeg_path.text().strip(),
            soundfont_path=self.soundfont_path.text().strip(),
            theme=self.settings.theme,
            autosave_enabled=self.autosave.isChecked(),
            autosave_seconds=self.autosave_seconds.value(),
            master_volume=self.master_volume.value(),
            sample_rate=self.sample_rate.value(),
            buffer_size=self.buffer_size.value(),
            audio_device=str(self.audio_device.currentData()),
            latency_ms=self.latency_ms.value(),
        )
        shortcuts = {
            key: edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            for key, edit in self.shortcut_edits.items()
        }
        return settings, shortcuts
