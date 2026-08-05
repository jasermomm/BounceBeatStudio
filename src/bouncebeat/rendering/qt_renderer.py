from __future__ import annotations

import math
from typing import Mapping

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient

from bouncebeat.models.enums import BallAppearance, CameraMode
from bouncebeat.models.events import SimulationSnapshot
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.simulation.geometry import qt_ring_arc_degrees
from bouncebeat.models.scene import (
    BallObject,
    BaseObject,
    BumperObject,
    EmitterObject,
    ParticleSystemObject,
    PolygonObject,
    PortalObject,
    RingObject,
    TextOverlayObject,
    WallObject,
)


def _qcolor(value: str, alpha: float | None = None) -> QColor:
    color = QColor(value)
    if not color.isValid():
        color = QColor("#FFFFFF")
    if alpha is not None:
        color.setAlphaF(max(0.0, min(1.0, alpha)))
    return color


class SceneRenderer:
    def __init__(self) -> None:
        self.last_scale = 1.0
        self.last_offset = (0.0, 0.0)

    def render(
        self,
        project: BounceBeatProject,
        snapshot: SimulationSnapshot,
        models: Mapping[str, BaseObject],
        width: int | None = None,
        height: int | None = None,
        *,
        transparent: bool | None = None,
        show_grid: bool | None = None,
        show_safe_area: bool | None = None,
        show_stats: bool = True,
        actual_fps: float = 0.0,
        recording_text: str = "",
        view_zoom: float = 1.0,
        view_pan: tuple[float, float] = (0.0, 0.0),
    ) -> QImage:
        width = int(width or project.render.width)
        height = int(height or project.render.height)
        transparent = project.render.transparent if transparent is None else transparent
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent if transparent else _qcolor(project.render.background_color))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        logical_w = project.scene.logical_width
        logical_h = project.scene.logical_height
        camera_pan_x, camera_pan_y = project.camera.pan
        camera_zoom = max(0.05, project.camera.zoom)
        ball_states = [state for state in snapshot.object_states.values() if state.radius > 0 and state.visible]
        if project.camera.mode == CameraMode.FOLLOW_SELECTED and project.camera.follow_object_id:
            followed = snapshot.object_states.get(project.camera.follow_object_id)
            if followed is not None:
                camera_pan_x += logical_w / 2 - followed.position[0]
                camera_pan_y += logical_h / 2 - followed.position[1]
        elif project.camera.mode in {CameraMode.FOLLOW_AVERAGE, CameraMode.AUTO_ZOOM} and ball_states:
            average_x = sum(state.position[0] for state in ball_states) / len(ball_states)
            average_y = sum(state.position[1] for state in ball_states) / len(ball_states)
            camera_pan_x += logical_w / 2 - average_x
            camera_pan_y += logical_h / 2 - average_y
            if project.camera.mode == CameraMode.AUTO_ZOOM:
                left = min(state.position[0] - state.radius for state in ball_states)
                right = max(state.position[0] + state.radius for state in ball_states)
                top = min(state.position[1] - state.radius for state in ball_states)
                bottom = max(state.position[1] + state.radius for state in ball_states)
                spread_w = max(160.0, right - left)
                spread_h = max(160.0, bottom - top)
                camera_zoom *= min(logical_w * 0.82 / spread_w, logical_h * 0.82 / spread_h, 4.0)


        editor_zoom = max(0.05, float(view_zoom))
        view_pan_x, view_pan_y = view_pan
        scale = min(width / logical_w, height / logical_h) * camera_zoom * editor_zoom
        shake = snapshot.camera_shake * max(0.0, project.camera.shake_intensity)
        shake_x = math.sin(snapshot.time * 97.0 + 0.7) * shake * 14.0
        shake_y = math.sin(snapshot.time * 83.0 + 2.1) * shake * 14.0
        offset_x = (width - logical_w * scale) / 2 + (camera_pan_x + view_pan_x + shake_x) * scale
        offset_y = (height - logical_h * scale) / 2 + (camera_pan_y + view_pan_y + shake_y) * scale
        self.last_scale = scale
        self.last_offset = (offset_x, offset_y)
        painter.translate(offset_x, offset_y)
        painter.scale(scale, scale)

        if show_grid if show_grid is not None else project.render.show_grid:
            self._draw_grid(painter, project)
        if show_safe_area if show_safe_area is not None else project.render.show_safe_area:
            self._draw_safe_area(painter, project)

        ordered = sorted(models.values(), key=lambda item: item.z_index)
        for model in ordered:
            if not model.visible:
                continue
            state = snapshot.object_states.get(model.id)
            if isinstance(model, WallObject):
                self._draw_wall(painter, model)
            elif isinstance(model, RingObject):
                self._draw_ring(painter, model, state)
            elif isinstance(model, BumperObject):
                self._draw_bumper(painter, model, state)
            elif isinstance(model, PolygonObject):
                self._draw_polygon(painter, model, state)
            elif isinstance(model, PortalObject):
                self._draw_portal(painter, model, state)
            elif isinstance(model, EmitterObject):
                self._draw_emitter(painter, model)
            elif isinstance(model, TextOverlayObject):
                self._draw_text(painter, model)
            elif isinstance(model, ParticleSystemObject):
                continue


        drawn_ids = {model.id for model in ordered}
        for object_id, state in snapshot.object_states.items():
            model = models.get(object_id)
            if isinstance(model, BallObject):
                self._draw_ball(painter, model, state)
            elif object_id not in drawn_ids and state.radius > 0:
                synthetic = BallObject(id=object_id, radius=state.radius, color=state.color)
                self._draw_ball(painter, synthetic, state)

        self._draw_effects(painter, snapshot)
        painter.resetTransform()
        if show_stats:
            self._draw_overlay(painter, project, snapshot, actual_fps, recording_text)
        painter.end()
        return image

    def logical_from_pixel(self, point: QPointF) -> QPointF:
        if self.last_scale <= 0:
            return point
        return QPointF(
            (point.x() - self.last_offset[0]) / self.last_scale,
            (point.y() - self.last_offset[1]) / self.last_scale,
        )

    def _draw_grid(self, painter: QPainter, project: BounceBeatProject) -> None:
        pen = QPen(_qcolor(project.scene.palette.guide, 0.18), 1.0)
        painter.setPen(pen)
        step = 60
        for x in range(0, round(project.scene.logical_width) + 1, step):
            painter.drawLine(QPointF(x, 0), QPointF(x, project.scene.logical_height))
        for y in range(0, round(project.scene.logical_height) + 1, step):
            painter.drawLine(QPointF(0, y), QPointF(project.scene.logical_width, y))

    def _draw_safe_area(self, painter: QPainter, project: BounceBeatProject) -> None:
        margin_x = project.scene.logical_width * 0.08
        margin_y = project.scene.logical_height * 0.08
        painter.setPen(QPen(_qcolor(project.scene.palette.guide, 0.7), 2, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(margin_x, margin_y, project.scene.logical_width - margin_x * 2, project.scene.logical_height - margin_y * 2))

    def _draw_wall(self, painter: QPainter, model: WallObject) -> None:
        pen = QPen(_qcolor(model.color), model.thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(*model.start), QPointF(*model.end))

    def _draw_ring(self, painter: QPainter, model: RingObject, state) -> None:
        position = state.position if state else model.position
        radius = state.radius if state and state.radius else model.radius
        rotation = state.rotation if state else model.rotation + model.opening_rotation
        rect = QRectF(position[0] - radius, position[1] - radius, radius * 2, radius * 2)
        start_degrees, span_degrees = qt_ring_arc_degrees(rotation, model.opening_angle)

        def draw_ring_path(width: float, color: QColor) -> None:
            painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            if model.opening_angle <= 0:
                painter.drawEllipse(rect)
            else:
                painter.drawArc(rect, round(start_degrees * 16), round(span_degrees * 16))

        if model.glow > 0:
            for factor, alpha in ((1.55, 0.05), (1.3, 0.09), (1.13, 0.15)):
                draw_ring_path(model.thickness * factor, _qcolor(model.color, alpha * model.glow))
        draw_ring_path(model.thickness, _qcolor(model.color))

    def _draw_bumper(self, painter: QPainter, model: BumperObject, state) -> None:
        position = state.position if state else model.position
        gradient = QRadialGradient(QPointF(*position), model.radius)
        gradient.setColorAt(0.0, _qcolor("#FFFFFF", 0.95))
        gradient.setColorAt(0.35, _qcolor(model.color, 0.95))
        gradient.setColorAt(1.0, _qcolor(model.color, 0.35))
        painter.setBrush(gradient)
        painter.setPen(QPen(_qcolor(model.color), 5))
        painter.drawEllipse(QPointF(*position), model.radius, model.radius)

    def _draw_polygon(self, painter: QPainter, model: PolygonObject, state) -> None:
        position = state.position if state else model.position
        rotation = math.radians(state.rotation if state else model.rotation)
        cos_a, sin_a = math.cos(rotation), math.sin(rotation)
        points = []
        for x, y in model.vertices:
            points.append(QPointF(position[0] + x * cos_a - y * sin_a, position[1] + x * sin_a + y * cos_a))
        painter.setBrush(_qcolor(model.color, 0.82))
        painter.setPen(QPen(_qcolor(model.color), 3))
        painter.drawPolygon(QPolygonF(points))

    def _draw_portal(self, painter: QPainter, model: PortalObject, state) -> None:
        position = state.position if state else model.position
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for inset, alpha, width in ((0, 1.0, 6), (10, 0.55, 4), (20, 0.25, 3)):
            radius = max(3, model.radius - inset)
            painter.setPen(QPen(_qcolor(model.color, alpha), width))
            painter.drawEllipse(QPointF(*position), radius, radius)

    def _draw_emitter(self, painter: QPainter, model: EmitterObject) -> None:
        painter.setPen(QPen(_qcolor(model.color, 0.8), 3, Qt.PenStyle.DashLine))
        painter.setBrush(_qcolor(model.color, 0.08))
        width, height = model.spawn_area
        painter.drawRect(QRectF(model.position[0] - width / 2, model.position[1] - height / 2, max(16, width), max(16, height)))

    def _draw_text(self, painter: QPainter, model: TextOverlayObject) -> None:
        painter.save()
        painter.setOpacity(model.opacity)
        painter.setPen(_qcolor(model.color))
        font = QFont("Segoe UI", max(6, round(model.font_size)))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        rect = QRectF(model.position[0] - 450, model.position[1] - model.font_size, 900, model.font_size * 2.5)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, model.text)
        painter.restore()

    def _draw_ball(self, painter: QPainter, model: BallObject, state) -> None:
        if state is None or not state.visible:
            return
        trail = state.trail
        if model.trail_enabled and len(trail) > 1:
            path = QPainterPath(QPointF(*trail[0]))
            for point in trail[1:]:
                path.lineTo(QPointF(*point))
            painter.setPen(QPen(
                _qcolor(state.color, model.trail_opacity),
                model.trail_thickness,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            ))
            painter.drawPath(path)

        base_radius = state.radius if getattr(state, "radius", 0.0) > 0 else model.radius
        radius = base_radius * (1.0 + state.size_pulse * 0.18)
        appearance = getattr(model.appearance, "value", str(model.appearance))
        glow = max(model.glow, state.glow_pulse)
        if appearance == BallAppearance.NEON.value:
            glow = max(glow, 0.65)
        if glow > 0:
            for factor, alpha in ((2.0, 0.04), (1.55, 0.08), (1.25, 0.16)):
                painter.setBrush(_qcolor(state.color, alpha * glow))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(*state.position), radius * factor, radius * factor)

        base_color = _qcolor(state.color)
        shading = max(0.0, min(1.0, model.shading_strength))
        if appearance == BallAppearance.FLAT.value:
            painter.setBrush(base_color)
        elif appearance == BallAppearance.NEON.value:
            core = QColor(base_color)
            core = core.darker(round(145 + shading * 55))
            painter.setBrush(core)
        else:
            focal = QPointF(
                state.position[0] - radius * 0.20,
                state.position[1] - radius * 0.24,
            )
            gradient = QRadialGradient(focal, radius * 1.45)
            center = QColor(base_color).lighter(round(100 + shading * 38))
            edge = QColor(base_color).darker(round(100 + shading * 62))
            gradient.setColorAt(0.0, center)
            gradient.setColorAt(0.48, base_color)
            gradient.setColorAt(1.0, edge)
            painter.setBrush(gradient)

        if model.outline_enabled:
            outline = _qcolor(model.outline_color, model.outline_opacity)
            width = max(0.0, float(model.outline_width))
            if appearance == BallAppearance.NEON.value:
                outline = _qcolor(state.color, max(model.outline_opacity, 0.9))
                width = max(width, radius * 0.075)
            painter.setPen(QPen(outline, width))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(*state.position), radius, radius)

        if model.reflections_enabled and model.reflection_strength > 0:
            painter.save()
            clip = QPainterPath()
            clip.addEllipse(QPointF(*state.position), radius, radius)
            painter.setClipPath(clip)
            offset_x, offset_y = model.reflection_offset
            highlight_center = QPointF(
                state.position[0] + radius * offset_x,
                state.position[1] + radius * offset_y,
            )
            highlight_radius = max(1.0, radius * max(0.05, model.reflection_size))
            reflection = QRadialGradient(highlight_center, highlight_radius)
            strength = max(0.0, min(1.0, model.reflection_strength))
            reflection.setColorAt(0.0, _qcolor("#FFFFFF", 0.82 * strength))
            reflection.setColorAt(0.42, _qcolor("#FFFFFF", 0.36 * strength))
            reflection.setColorAt(1.0, _qcolor("#FFFFFF", 0.0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(reflection)
            painter.drawEllipse(
                highlight_center,
                highlight_radius,
                highlight_radius * 0.68,
            )
            painter.restore()

    def _draw_effects(self, painter: QPainter, snapshot: SimulationSnapshot) -> None:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for ripple in snapshot.ripples:
            alpha = max(0.0, 1.0 - ripple.age / max(0.001, ripple.lifetime))
            painter.setPen(QPen(_qcolor(ripple.color, alpha * 0.75), max(1.0, 7.0 * alpha)))
            painter.drawEllipse(QPointF(*ripple.position), ripple.radius, ripple.radius)
        painter.setPen(Qt.PenStyle.NoPen)
        for particle in snapshot.particles:
            alpha = max(0.0, 1.0 - particle.age / max(0.001, particle.lifetime))
            painter.setBrush(_qcolor(particle.color, alpha))
            painter.drawEllipse(QPointF(*particle.position), particle.radius, particle.radius)

    def _draw_overlay(self, painter: QPainter, project: BounceBeatProject, snapshot: SimulationSnapshot, actual_fps: float, recording_text: str) -> None:
        if not project.render.show_fps and not recording_text:
            return
        painter.setFont(QFont("Consolas", max(9, round(project.render.width / 85))))
        lines = []
        if project.render.show_fps:
            lines.extend([
                f"FPS {actual_fps:5.1f} / {project.render.fps}",
                f"Frame time {(1000.0 / actual_fps) if actual_fps > 0 else 0.0:5.1f} ms",
                f"Frame {snapshot.frame:,}",
                f"Time {snapshot.time:7.2f}s",
                f"Balls {snapshot.active_ball_count}",
                f"Collisions {snapshot.collision_count:,}",
                f"Physics {snapshot.physics_hz} Hz",
                f"Dropped {snapshot.dropped_frames:,}",
            ])
            if snapshot.current_notes:
                lines.append("Notes " + ", ".join(str(note) for note in snapshot.current_notes[-8:]))
        if recording_text:
            lines.append(recording_text)
        metrics = painter.fontMetrics()
        width = max((metrics.horizontalAdvance(line) for line in lines), default=0) + 26
        height = metrics.height() * len(lines) + 22
        rect = QRectF(18, 18, width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_qcolor("#050814", 0.72))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(_qcolor("#F8FAFC"))
        y = 18 + 14 + metrics.ascent()
        for line in lines:
            painter.drawText(QPointF(31, y), line)
            y += metrics.height()
