from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QDialog, QGridLayout, QLabel, QPushButton, QVBoxLayout

from bouncebeat.presets.builtin import PRESET_NAMES
from bouncebeat.utilities.ffmpeg import FFmpegInfo


class WelcomeDialog(QDialog):
    create_blank = Signal()
    open_project = Signal()
    import_midi = Signal()
    preset_requested = Signal(str)

    def __init__(self, ffmpeg: FFmpegInfo, soundfont_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to BounceBeat Studio")
        self.resize(650, 520)
        layout = QVBoxLayout(self)
        title = QLabel("<h1>BounceBeat Studio</h1><p>Create musical physics simulations, preview them live, and export synchronized vertical or landscape videos.</p>")
        title.setWordWrap(True)
        layout.addWidget(title)
        grid = QGridLayout()
        blank = QPushButton("Create blank project")
        open_button = QPushButton("Open project")
        midi_button = QPushButton("Import MIDI")
        self.preset_combo = QComboBox(); self.preset_combo.addItems(PRESET_NAMES)
        preset_button = QPushButton("Open example preset")
        grid.addWidget(blank, 0, 0); grid.addWidget(open_button, 0, 1)
        grid.addWidget(midi_button, 1, 0); grid.addWidget(self.preset_combo, 1, 1)
        grid.addWidget(preset_button, 2, 0, 1, 2)
        layout.addLayout(grid)
        ffmpeg_text = "Ready" if ffmpeg.available else "Not found — video export disabled until configured"
        soundfont_text = soundfont_path if soundfont_path else "Not selected — built-in synthesizer will be used"
        status = QLabel(f"<b>FFmpeg:</b> {ffmpeg_text}<br><b>SoundFont:</b> {soundfont_text}")
        status.setWordWrap(True)
        layout.addWidget(status)
        tutorial = QLabel(
            "<b>Guided workflow</b><br>1. Import MIDI.<br>2. Select one or more playable tracks.<br>"
            "3. Choose a preset.<br>4. Assign tracks and customize colors.<br>5. Choose resolution and FPS.<br>"
            "6. Preview the simulation and adjust physics or MIDI mapping as needed.<br>"
            "7. Record in real time or render offline."
        )
        tutorial.setWordWrap(True)
        layout.addWidget(tutorial)
        close_button = QPushButton("Continue to editor")
        layout.addWidget(close_button)
        blank.clicked.connect(lambda: (self.create_blank.emit(), self.accept()))
        open_button.clicked.connect(lambda: (self.open_project.emit(), self.accept()))
        midi_button.clicked.connect(lambda: (self.import_midi.emit(), self.accept()))
        preset_button.clicked.connect(lambda: (self.preset_requested.emit(self.preset_combo.currentText()), self.accept()))
        close_button.clicked.connect(self.accept)
