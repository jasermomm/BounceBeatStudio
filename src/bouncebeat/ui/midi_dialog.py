from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from bouncebeat.models.midi import MidiAsset


class MidiInspectorDialog(QDialog):
    preview_requested = Signal(str)

    def __init__(self, asset: MidiAsset, selected_ids: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.asset = asset
        self._selected_ids = set(selected_ids or [])
        self.setWindowTitle("MIDI Track Inspector")
        self.resize(1050, 560)
        layout = QVBoxLayout(self)
        intro = QLabel(
            f"{len(asset.tracks)} tracks • {len(asset.playable_tracks())} playable • {asset.duration:.2f} seconds. "
            "Choose one or more tracks; each can later be assigned to a different ball or surface."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search tracks or instruments…")
        self.select_all = QPushButton("Select all playable")
        self.select_none = QPushButton("Clear")
        self.preview = QPushButton("Preview selected row")
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.select_all)
        toolbar.addWidget(self.select_none)
        toolbar.addWidget(self.preview)
        layout.addLayout(toolbar)
        self.table = QTableWidget(0, 15)
        self.table.setHorizontalHeaderLabels([
            "Use", "Mute", "Solo", "Volume", "Pan", "#", "Track name", "Channel", "Instrument", "Program", "Notes",
            "Range", "Duration", "Drums", "Status",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self._filter)
        self.select_all.clicked.connect(self._select_all)
        self.select_none.clicked.connect(self._select_none)
        self.preview.clicked.connect(self._preview)
        self.table.doubleClicked.connect(lambda _index: self._preview())
        self._populate()

    def _populate(self) -> None:
        self.table.setRowCount(len(self.asset.tracks))
        for row, track in enumerate(self.asset.tracks):
            use = QTableWidgetItem()
            use.setFlags(use.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            use.setCheckState(Qt.CheckState.Checked if track.id in self._selected_ids else Qt.CheckState.Unchecked)
            if track.note_count == 0:
                use.setFlags(use.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            use.setData(Qt.ItemDataRole.UserRole, track.id)
            self.table.setItem(row, 0, use)
            for column, checked in ((1, track.muted), (2, track.solo)):
                toggle = QTableWidgetItem()
                toggle.setFlags(toggle.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                toggle.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                if track.note_count == 0:
                    toggle.setFlags(toggle.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row, column, toggle)
            volume = QDoubleSpinBox()
            volume.setRange(0.0, 2.0)
            volume.setSingleStep(0.05)
            volume.setDecimals(2)
            volume.setValue(track.volume)
            volume.setEnabled(track.note_count > 0)
            self.table.setCellWidget(row, 3, volume)
            pan = QDoubleSpinBox()
            pan.setRange(-1.0, 1.0)
            pan.setSingleStep(0.1)
            pan.setDecimals(2)
            pan.setValue(track.pan)
            pan.setEnabled(track.note_count > 0)
            self.table.setCellWidget(row, 4, pan)
            values = [
                str(track.index), track.name, str(track.channel + 1), track.instrument_name,
                str(track.program), str(track.note_count),
                "—" if track.lowest_note is None else f"{track.lowest_note}–{track.highest_note}",
                f"{track.duration:.2f}s", "Yes" if track.is_drum else "No",
                "Playable" if track.note_count else "Metadata only" if track.is_metadata_only else "Empty",
            ]
            for column, value in enumerate(values, start=5):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def selected_track_ids(self) -> list[str]:
        result = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def _select_all(self) -> None:
        for row, track in enumerate(self.asset.tracks):
            if track.note_count:
                self.table.item(row, 0).setCheckState(Qt.CheckState.Checked)

    def _select_none(self) -> None:
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for row, track in enumerate(self.asset.tracks):
            haystack = f"{track.name} {track.instrument_name} {track.index} {track.channel + 1}".lower()
            self.table.setRowHidden(row, needle not in haystack)

    def _preview(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        track_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        track = self.asset.get_track(track_id)
        if track and track.note_count:
            self.preview_requested.emit(track_id)

    def _accept(self) -> None:
        if self.asset.playable_tracks() and not self.selected_track_ids():
            QMessageBox.information(self, "Select a track", "Choose at least one playable MIDI track.")
            return
        for row, track in enumerate(self.asset.tracks):
            track.muted = self.table.item(row, 1).checkState() == Qt.CheckState.Checked
            track.solo = self.table.item(row, 2).checkState() == Qt.CheckState.Checked
            volume = self.table.cellWidget(row, 3)
            pan = self.table.cellWidget(row, 4)
            if isinstance(volume, QDoubleSpinBox):
                track.volume = volume.value()
            if isinstance(pan, QDoubleSpinBox):
                track.pan = pan.value()
        self.accept()
