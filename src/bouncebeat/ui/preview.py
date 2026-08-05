from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPaintEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QWidget

from bouncebeat.models.events import SimulationSnapshot
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.models.scene import BallObject, BaseObject, BumperObject, PortalObject, RingObject
from bouncebeat.rendering.qt_renderer import SceneRenderer


class PreviewWidget(QWidget):
    object_selected = Signal(str)
    object_moved = Signal(str, object)
    zoom_requested = Signal(float)
    view_changed = Signal(float)
    play_pause_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(420, 420)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.renderer = SceneRenderer()
        self.project: BounceBeatProject | None = None
        self.snapshot: SimulationSnapshot | None = None
        self.models: dict[str, BaseObject] = {}
        self.selected_id: str | None = None
        self.edit_mode = True
        self.simulation_playing = False
        self.actual_fps = 0.0
        self.recording_text = ""


        self.view_zoom = 1.6
        self.view_pan: tuple[float, float] = (0.0, 0.0)

        self._last_paint = time.perf_counter()
        self._dragging_id: str | None = None
        self._drag_offset = QPointF()
        self._panning = False
        self._pan_start_pixel = QPointF()
        self._pan_start_value: tuple[float, float] = (0.0, 0.0)

    def set_scene(
        self,
        project: BounceBeatProject,
        snapshot: SimulationSnapshot,
        models: dict[str, BaseObject],
        selected_id: str | None,
        actual_fps: float,
        recording_text: str = "",
    ) -> None:
        self.project = project
        self.snapshot = snapshot
        self.models = models
        self.selected_id = selected_id
        self.actual_fps = actual_fps
        self.recording_text = recording_text
        self.update()

    def set_view_zoom(self, value: float) -> None:
        self.view_zoom = max(0.2, min(12.0, float(value)))
        self.view_changed.emit(self.view_zoom)
        self.update()

    def zoom_by(self, factor: float) -> None:
        self.set_view_zoom(self.view_zoom * factor)

    def fit_canvas(self) -> None:
        self.view_pan = (0.0, 0.0)
        self.set_view_zoom(1.0)

    def fit_width(self) -> None:
        if self.project is None:
            return
        logical_w = max(1.0, self.project.scene.logical_width)
        logical_h = max(1.0, self.project.scene.logical_height)
        base_fit = min(self.width() / logical_w, self.height() / logical_h)
        camera_zoom = max(0.05, self.project.camera.zoom)
        desired_scale = max(0.01, self.width() * 0.94 / logical_w)
        self.view_pan = (0.0, 0.0)
        self.set_view_zoom(desired_scale / max(0.0001, base_fit * camera_zoom))

    def actual_pixels(self) -> None:
        """Show one logical scene pixel as one editor pixel."""
        if self.project is None:
            return
        logical_w = max(1.0, self.project.scene.logical_width)
        logical_h = max(1.0, self.project.scene.logical_height)
        base_fit = min(self.width() / logical_w, self.height() / logical_h)
        camera_zoom = max(0.05, self.project.camera.zoom)
        self.view_pan = (0.0, 0.0)
        self.set_view_zoom(1.0 / max(0.0001, base_fit * camera_zoom))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        if self.project is None or self.snapshot is None:
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Open a project or choose a preset")
            return
        image = self.renderer.render(
            self.project,
            self.snapshot,
            self.models,
            max(1, self.width()),
            max(1, self.height()),
            show_stats=True,
            actual_fps=self.actual_fps,
            recording_text=self.recording_text,
            view_zoom=self.view_zoom,
            view_pan=self.view_pan,
        )
        painter.drawImage(0, 0, image)
        if self.selected_id and self.selected_id in self.snapshot.object_states:
            state = self.snapshot.object_states[self.selected_id]
            logical = QPointF(*state.position)
            x = logical.x() * self.renderer.last_scale + self.renderer.last_offset[0]
            y = logical.y() * self.renderer.last_scale + self.renderer.last_offset[1]
            radius = max(12.0, state.radius * self.renderer.last_scale + 8)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = painter.pen()
            pen.setColor(Qt.GlobalColor.white)
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawEllipse(QPointF(x, y), radius, radius)
        self._last_paint = time.perf_counter()

    def _hit_test(self, logical: QPointF) -> str | None:
        if self.snapshot is None:
            return None
        best: tuple[float, str] | None = None
        for object_id, state in self.snapshot.object_states.items():
            model = self.models.get(object_id)
            if model is None or model.locked or not model.visible:
                continue
            distance = math.dist((logical.x(), logical.y()), state.position)
            radius = state.radius or getattr(model, "radius", 28.0)
            if isinstance(model, RingObject):
                hit = abs(distance - radius) <= max(18.0, model.thickness * 1.8)
                score = abs(distance - radius)
            elif isinstance(model, (BallObject, BumperObject, PortalObject)):
                hit = distance <= radius + 12
                score = distance
            else:
                hit = distance <= 90
                score = distance
            if hit and (best is None or score < best[0]):
                best = (score, object_id)
        return best[1] if best else None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        wants_pan = event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        )
        if wants_pan:
            self._panning = True
            self._pan_start_pixel = event.position()
            self._pan_start_value = self.view_pan
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() != Qt.MouseButton.LeftButton or self.project is None:
            return super().mousePressEvent(event)
        logical = self.renderer.logical_from_pixel(event.position())
        object_id = self._hit_test(logical)
        if object_id:
            self.object_selected.emit(object_id)
            self.selected_id = object_id
            model = self.models.get(object_id)
            state = self.snapshot.object_states.get(object_id) if self.snapshot else None
            if self.edit_mode and not self.simulation_playing and model and state and not model.locked:
                self._dragging_id = object_id
                self._drag_offset = logical - QPointF(*state.position)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            delta = event.position() - self._pan_start_pixel
            scale = max(0.0001, self.renderer.last_scale)
            self.view_pan = (
                self._pan_start_value[0] + delta.x() / scale,
                self._pan_start_value[1] + delta.y() / scale,
            )
            self.update()
            event.accept()
            return
        if not self._dragging_id:
            return super().mouseMoveEvent(event)
        logical = self.renderer.logical_from_pixel(event.position()) - self._drag_offset
        if self.project:
            x = max(0.0, min(self.project.scene.logical_width, logical.x()))
            y = max(0.0, min(self.project.scene.logical_height, logical.y()))
            self.object_moved.emit(self._dragging_id, (x, y))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        self._dragging_id = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_pause_requested.emit()

    def wheelEvent(self, event: QWheelEvent) -> None:
        amount = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_requested.emit(amount)
        event.accept()
