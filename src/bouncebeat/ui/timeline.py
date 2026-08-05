from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from bouncebeat.models.events import PhysicsEvent
from bouncebeat.models.project import BounceBeatProject


class TimelineWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.project: BounceBeatProject | None = None
        self.events: list[PhysicsEvent] = []
        self.current_time = 0.0
        self.seconds_per_pixel = 0.03
        self.offset_seconds = 0.0

    def set_data(self, project: BounceBeatProject, events: list[PhysicsEvent], current_time: float) -> None:
        self.project = project
        self.events = list(events[-5000:])
        self.current_time = current_time
        self.update()

    def _x(self, seconds: float) -> float:
        return (seconds - self.offset_seconds) / self.seconds_per_pixel

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0B1020"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if not self.project:
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "MIDI and physics events appear here")
            return
        ruler_height = 28
        painter.fillRect(QRectF(0, 0, self.width(), ruler_height), QColor("#151C2D"))
        recording_start = self.project.timeline.start_seconds
        recording_end = self.project.timeline.end_seconds or self.project.recording.duration_seconds
        range_x = self._x(recording_start)
        range_width = max(0.0, self._x(recording_end) - range_x)
        recording_color = QColor("#2563EB"); recording_color.setAlpha(24)
        painter.fillRect(QRectF(range_x, ruler_height, range_width, self.height() - ruler_height), recording_color)
        if self.project.timeline.loop_end_seconds > self.project.timeline.loop_start_seconds:
            loop_x = self._x(self.project.timeline.loop_start_seconds)
            loop_width = self._x(self.project.timeline.loop_end_seconds) - loop_x
            loop_color = QColor("#A855F7"); loop_color.setAlpha(28)
            painter.fillRect(QRectF(loop_x, ruler_height, loop_width, self.height() - ruler_height), loop_color)
        visible_seconds = self.width() * self.seconds_per_pixel
        major = 1.0
        if visible_seconds > 120:
            major = 10.0
        elif visible_seconds > 45:
            major = 5.0
        elif visible_seconds < 8:
            major = 0.5
        start_tick = math.floor(self.offset_seconds / major) * major
        painter.setFont(QFont("Segoe UI", 8))
        tick = start_tick
        while tick <= self.offset_seconds + visible_seconds + major:
            x = self._x(tick)
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.drawLine(round(x), 0, round(x), self.height())
            painter.setPen(QColor("#CBD5E1"))
            painter.drawText(round(x + 4), 18, f"{tick:g}s")
            tick += major

        lane_height = max(16, (self.height() - ruler_height - 18) / max(1, len(self.project.midi_asset.playable_tracks())))
        tracks = self.project.midi_asset.playable_tracks()
        track_lanes = {track.id: index for index, track in enumerate(tracks)}
        palette = self.project.scene.palette.colors
        for track in tracks:
            lane = track_lanes[track.id]
            y = ruler_height + lane * lane_height
            painter.setPen(QColor("#1F2937"))
            painter.drawLine(0, round(y + lane_height), self.width(), round(y + lane_height))
            color = QColor(palette[lane % len(palette)])
            color.setAlpha(185)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            for note in track.notes:
                x = self._x(note.start)
                width = max(2.0, note.duration / self.seconds_per_pixel)
                if x + width < 0 or x > self.width():
                    continue
                pitch_offset = (note.pitch - (track.lowest_note or note.pitch)) % 12
                note_y = y + 2 + (pitch_offset / 12) * max(2, lane_height - 7)
                painter.drawRoundedRect(QRectF(x, note_y, width, max(3, lane_height * 0.18)), 1.5, 1.5)

        event_colors = {
            "collision": QColor("#F87171"),
            "ball_creation": QColor("#34D399"),
            "ball_deletion": QColor("#F59E0B"),
            "object_deletion": QColor("#F59E0B"),
            "portal": QColor("#A78BFA"),
        }
        for physics_event in self.events:
            x = self._x(physics_event.time)
            if 0 <= x <= self.width():
                painter.setPen(QPen(event_colors.get(physics_event.event_type, QColor("#F87171")), 2))
                painter.drawLine(round(x), ruler_height, round(x), self.height())
        current_x = self._x(self.current_time)
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawLine(round(current_x), 0, round(current_x), self.height())

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 0.8 if event.angleDelta().y() > 0 else 1.25
            anchor_time = self.offset_seconds + event.position().x() * self.seconds_per_pixel
            self.seconds_per_pixel = max(0.002, min(2.0, self.seconds_per_pixel * factor))
            self.offset_seconds = max(0.0, anchor_time - event.position().x() * self.seconds_per_pixel)
        else:
            delta = -event.angleDelta().y() / 120 * self.seconds_per_pixel * 100
            self.offset_seconds = max(0.0, self.offset_seconds + delta)
        self.update()
