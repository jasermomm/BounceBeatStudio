from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bouncebeat.models.enums import (
    BallAppearance, CameraMode, ColorMode, DuplicationMode, DuplicationSpawnMode, DuplicationTrigger,
    DuplicationVelocityMode, MidiMappingMode, Waveform,
)
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.models.scene import (
    BallObject,
    BaseObject,
    BumperObject,
    EmitterObject,
    PolygonObject,
    PortalObject,
    RingObject,
    TextOverlayObject,
    WallObject,
)
from bouncebeat.utilities.colors import ColorParseError, parse_color_list


class PropertiesPanel(QWidget):
    object_property_changed = Signal(str, str, object)
    project_property_changed = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.project: BounceBeatProject | None = None
        self.object: BaseObject | None = None
        self._project_bindings: dict[str, tuple[QWidget, str]] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.object_scroll = QScrollArea()
        self.object_scroll.setWidgetResizable(True)
        self.object_container = QWidget()
        self.object_layout = QFormLayout(self.object_container)
        self.object_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.object_scroll.setWidget(self.object_container)
        self.tabs.addTab(self.object_scroll, "Object")
        self.project_scroll = QScrollArea()
        self.project_scroll.setWidgetResizable(True)
        self.project_container = QWidget()
        self.project_layout = QFormLayout(self.project_container)
        self.project_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.project_scroll.setWidget(self.project_container)
        self.tabs.addTab(self.project_scroll, "Project")
        self._build_project_tab()

    def _clear_layout(self, layout: QFormLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def _double(self, value: float, minimum=-100000.0, maximum=100000.0, decimals=2, step=1.0) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setSingleStep(step)
        widget.setValue(float(value))
        widget.setKeyboardTracking(False)
        return widget

    def _integer(self, value: int, minimum=-100000, maximum=100000) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(int(value))
        widget.setKeyboardTracking(False)
        return widget

    def _emit_object(self, name: str, value) -> None:
        if self.object:
            self.object_property_changed.emit(self.object.id, name, value)

    def _bind_double(self, label: str, name: str, value: float, minimum=-100000.0, maximum=100000.0, decimals=2, step=1.0) -> QDoubleSpinBox:
        widget = self._double(value, minimum, maximum, decimals, step)
        widget.editingFinished.connect(lambda n=name, w=widget: self._emit_object(n, w.value()))
        self.object_layout.addRow(label, widget)
        return widget

    def _bind_int(self, label: str, name: str, value: int, minimum=-100000, maximum=100000) -> QSpinBox:
        widget = self._integer(value, minimum, maximum)
        widget.editingFinished.connect(lambda n=name, w=widget: self._emit_object(n, w.value()))
        self.object_layout.addRow(label, widget)
        return widget

    def _bind_check(self, label: str, name: str, value: bool) -> QCheckBox:
        widget = QCheckBox()
        widget.setChecked(bool(value))
        widget.toggled.connect(lambda checked, n=name: self._emit_object(n, checked))
        self.object_layout.addRow(label, widget)
        return widget

    def _bind_combo(self, label: str, name: str, value: str, values: list[tuple[str, str]]) -> QComboBox:
        widget = QComboBox()
        for display, data in values:
            widget.addItem(display, data)
        index = widget.findData(value)
        widget.setCurrentIndex(max(0, index))
        widget.currentIndexChanged.connect(lambda _index, n=name, w=widget: self._emit_object(n, w.currentData()))
        self.object_layout.addRow(label, widget)
        return widget

    def _position_row(self, obj: BaseObject) -> None:
        row = QHBoxLayout()
        x = self._double(obj.position[0], 0, self.project.scene.logical_width if self.project else 10000)
        y = self._double(obj.position[1], 0, self.project.scene.logical_height if self.project else 10000)
        x.setPrefix("X ")
        y.setPrefix("Y ")
        row.addWidget(x)
        row.addWidget(y)
        emit = lambda: self._emit_object("position", (x.value(), y.value()))
        x.editingFinished.connect(emit)
        y.editingFinished.connect(emit)
        self.object_layout.addRow("Position", row)

    def _velocity_row(self, ball: BallObject) -> None:
        row = QHBoxLayout()
        x = self._double(ball.initial_velocity[0], -5000, 5000)
        y = self._double(ball.initial_velocity[1], -5000, 5000)
        x.setPrefix("X ")
        y.setPrefix("Y ")
        row.addWidget(x)
        row.addWidget(y)
        emit = lambda: self._emit_object("initial_velocity", (x.value(), y.value()))
        x.editingFinished.connect(emit)
        y.editingFinished.connect(emit)
        self.object_layout.addRow("Initial velocity", row)

    def _bind_vec2(
        self, label: str, name: str, value: tuple[float, float],
        minimum: float = -100000.0, maximum: float = 100000.0,
        first_prefix: str = "X ", second_prefix: str = "Y ", decimals: int = 2, step: float = 1.0,
    ) -> None:
        row = QHBoxLayout()
        first = self._double(value[0], minimum, maximum, decimals, step)
        second = self._double(value[1], minimum, maximum, decimals, step)
        first.setPrefix(first_prefix); second.setPrefix(second_prefix)
        row.addWidget(first); row.addWidget(second)
        emit = lambda: self._emit_object(name, (first.value(), second.value()))
        first.editingFinished.connect(emit); second.editingFinished.connect(emit)
        self.object_layout.addRow(label, row)

    def _bind_color(self, label: str, name: str, value: str) -> None:
        row = QHBoxLayout()
        line = QLineEdit(value)
        swatch = QPushButton("Choose")
        swatch.setStyleSheet(f"background:{value};")

        def emit() -> None:
            text = line.text().strip()
            color = QColor(text)
            if color.isValid():
                normalized = color.name(QColor.NameFormat.HexRgb).upper()
                line.setText(normalized)
                swatch.setStyleSheet(f"background:{normalized};")
                self._emit_object(name, normalized)

        def choose() -> None:
            color = QColorDialog.getColor(QColor(line.text()), self, f"Choose {label.lower()}")
            if color.isValid():
                line.setText(color.name(QColor.NameFormat.HexRgb).upper())
                emit()

        swatch.clicked.connect(choose)
        line.editingFinished.connect(emit)
        row.addWidget(line)
        row.addWidget(swatch)
        self.object_layout.addRow(label, row)

    def _color_row(self, obj: BaseObject) -> None:
        self._bind_color("Color", "color", obj.color)

    def _track_list(self, obj: BaseObject) -> None:
        widget = QListWidget()
        widget.setMaximumHeight(130)
        if self.project:
            for track in self.project.midi_asset.playable_tracks():
                item = QListWidgetItem(f"{track.name} — {track.instrument_name}")
                item.setData(Qt.ItemDataRole.UserRole, track.id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if track.id in obj.midi_track_ids else Qt.CheckState.Unchecked)
                widget.addItem(item)
        def changed(_item: QListWidgetItem) -> None:
            selected = []
            for index in range(widget.count()):
                item = widget.item(index)
                if item.checkState() == Qt.CheckState.Checked:
                    selected.append(item.data(Qt.ItemDataRole.UserRole))
            self._emit_object("midi_track_ids", selected)
        widget.itemChanged.connect(changed)
        self.object_layout.addRow("MIDI tracks", widget)

    def set_context(self, project: BounceBeatProject, obj: BaseObject | None) -> None:
        self.project = project
        self.object = obj
        self._build_object_tab()
        self._sync_project_tab()

    def _build_object_tab(self) -> None:
        self._clear_layout(self.object_layout)
        obj = self.object
        if obj is None:
            label = QLabel("Select an object in the scene hierarchy or preview.")
            label.setWordWrap(True)
            self.object_layout.addRow(label)
            return
        name = QLineEdit(obj.name)
        name.editingFinished.connect(lambda: self._emit_object("name", name.text().strip() or obj.name))
        self.object_layout.addRow("Name", name)
        self.object_layout.addRow("Type", QLabel(obj.kind.value.replace("_", " ").title()))
        self._position_row(obj)
        self._bind_double("Rotation", "rotation", obj.rotation, -36000, 36000, 2, 1)
        self._color_row(obj)
        self._bind_double("Glow", "glow", obj.glow, 0, 2, 2, 0.05)
        self._bind_check("Visible", "visible", obj.visible)
        self._bind_check("Locked", "locked", obj.locked)
        self._track_list(obj)
        midi_channel = self._integer(obj.midi_channel if obj.midi_channel is not None else -1, -1, 15)
        midi_channel.setSpecialValueText("Automatic")
        midi_channel.editingFinished.connect(lambda: self._emit_object("midi_channel", None if midi_channel.value() < 0 else midi_channel.value()))
        self.object_layout.addRow("MIDI channel", midi_channel)
        self._bind_check("Trigger notes", "midi_trigger", obj.midi_trigger)

        if isinstance(obj, BallObject):
            self._velocity_row(obj)
            self._bind_double("Radius", "radius", obj.radius, 2, 1000)
            self._bind_double("Mass", "mass", obj.mass, 0.01, 10000, 3, 0.1)
            self._bind_double("Maximum speed", "maximum_speed", obj.maximum_speed, 0, 20000)
            self._bind_double("Gravity scale", "gravity_scale", obj.gravity_scale, -10, 10, 3, 0.1)
            self._bind_double("Bounciness", "restitution", obj.restitution, 0, 2, 3, 0.02)
            self._bind_double("Friction", "friction", obj.friction, 0, 5, 3, 0.02)
            self._bind_double("Angular velocity", "angular_velocity", obj.angular_velocity, -5000, 5000)
            self._bind_combo(
                "Appearance",
                "appearance",
                getattr(obj.appearance, "value", BallAppearance.GLOSSY.value),
                [
                    ("Flat 2D", BallAppearance.FLAT.value),
                    ("Soft shaded", BallAppearance.SOFT_SHADED.value),
                    ("Glossy", BallAppearance.GLOSSY.value),
                    ("Neon", BallAppearance.NEON.value),
                ],
            )
            reflections = self._bind_check(
                "Reflections", "reflections_enabled", obj.reflections_enabled
            )
            reflections.setToolTip(
                "Adds a white reflected-light highlight without affecting physics. "
                "Turn this off for a completely flat 2D ball."
            )
            self._bind_double(
                "Reflection strength", "reflection_strength", obj.reflection_strength, 0, 1, 2, 0.05
            )
            self._bind_double(
                "Reflection size", "reflection_size", obj.reflection_size, 0.05, 1.2, 2, 0.05
            )
            self._bind_vec2(
                "Reflection offset", "reflection_offset", obj.reflection_offset, -1.0, 1.0,
                "X × radius ", "Y × radius ", 2, 0.05,
            )
            self._bind_double(
                "Shading strength", "shading_strength", obj.shading_strength, 0, 1, 2, 0.05
            )
            self._bind_check("Outline", "outline_enabled", obj.outline_enabled)
            self._bind_color("Outline color", "outline_color", obj.outline_color)
            self._bind_double(
                "Outline width", "outline_width", obj.outline_width, 0, 100, 2, 0.25
            )
            self._bind_double(
                "Outline opacity", "outline_opacity", obj.outline_opacity, 0, 1, 2, 0.05
            )
            self._bind_combo("Color behavior", "color_mode", obj.color_mode.value, [(item.value.replace("_", " ").title(), item.value) for item in ColorMode])
            self._bind_check("Color on collision", "change_color_on_collision", obj.change_color_on_collision)
            self._bind_check("Color on note", "change_color_on_note", obj.change_color_on_note)
            self._bind_check("Trail", "trail_enabled", obj.trail_enabled)
            self._bind_int("Trail length", "trail_length", obj.trail_length, 1, 1000)
            self._bind_double("Trail thickness", "trail_thickness", obj.trail_thickness, 0.1, 200)
            self._bind_double("Trail opacity", "trail_opacity", obj.trail_opacity, 0, 1, 2, 0.05)
            self._bind_combo("Duplication trigger", "duplication_trigger", obj.duplication_trigger.value, [(item.value.replace("_", " ").title(), item.value) for item in DuplicationTrigger])
            self._bind_combo("Duplication mode", "duplication_mode", obj.duplication_mode.value, [(item.value.replace("_", " ").title(), item.value) for item in DuplicationMode])
            self._bind_int("Every N collisions", "duplication_every_collisions", obj.duplication_every_collisions, 1, 10000)
            self._bind_double("Strength threshold", "duplication_strength_threshold", obj.duplication_strength_threshold, 0, 100000)
            target = QComboBox()
            target.addItem("None / any ring", "")
            if self.project:
                for candidate in self.project.scene.objects:
                    if candidate.id != obj.id:
                        target.addItem(candidate.name, candidate.id)
            target.setCurrentIndex(max(0, target.findData(obj.duplication_target_id or "")))
            target.currentIndexChanged.connect(lambda: self._emit_object("duplication_target_id", target.currentData() or None))
            self.object_layout.addRow("Duplication target", target)
            self._bind_int("Trigger MIDI note", "duplication_midi_note", obj.duplication_midi_note, 0, 127)
            self._bind_double("Interval seconds", "duplication_interval_seconds", obj.duplication_interval_seconds, 0.01, 86400, 3, 0.1)
            self._bind_double("Beat interval", "duplication_beat_interval", obj.duplication_beat_interval, 0.0625, 64, 4, 0.25)
            self._bind_combo(
                "New ball location", "duplication_spawn_mode", obj.duplication_spawn_mode.value,
                [(item.value.replace("_", " ").title(), item.value) for item in DuplicationSpawnMode],
            )
            spawn_target = QComboBox()
            spawn_target.addItem("None", "")
            if self.project:
                for candidate in self.project.scene.objects:
                    if candidate.id != obj.id:
                        spawn_target.addItem(candidate.name, candidate.id)
            spawn_target.setCurrentIndex(max(0, spawn_target.findData(obj.duplication_spawn_target_id or "")))
            spawn_target.currentIndexChanged.connect(
                lambda: self._emit_object("duplication_spawn_target_id", spawn_target.currentData() or None)
            )
            self.object_layout.addRow("Spawn target", spawn_target)
            self._bind_vec2("Custom spawn point", "duplication_spawn_position", obj.duplication_spawn_position, 0, 10000)
            self._bind_double("Spawn spread", "duplication_spawn_spread", obj.duplication_spawn_spread, 0, 5000)
            self._bind_combo(
                "New ball velocity", "duplication_velocity_mode", obj.duplication_velocity_mode.value,
                [(item.value.replace("_", " ").title(), item.value) for item in DuplicationVelocityMode],
            )
            spawn_count = self._bind_int(
                "Balls spawned per trigger", "duplication_spawn_count",
                obj.duplication_spawn_count, 1, 64,
            )
            spawn_count.setToolTip(
                "How many replacement balls this ball creates when its duplication trigger fires. "
                "Use 1 for normal respawn, 2 for doubling, or 3 for a 1→3→9 chain."
            )
            self._bind_check("Remove escaped source (respawn)", "remove_source_after_duplication", obj.remove_source_after_duplication)
            self._bind_check("Reset generation when respawning", "reset_generation_on_respawn", obj.reset_generation_on_respawn)
            max_triggers = self._bind_int(
                "Maximum trigger events per ball", "max_duplicates", obj.max_duplicates, 0, 10000
            )
            max_triggers.setToolTip(
                "Maximum times one source ball may activate duplication. Set this to 1 for death/respawn chains."
            )
            self._bind_int("Maximum generation", "max_generation", obj.max_generation, 0, 100)
            self._bind_check("Particles", "particles_enabled", obj.particles_enabled)
            self._bind_int("Particle count", "particle_count", obj.particle_count, 0, 10000)
            self._bind_double("Lifetime seconds", "lifetime_seconds", obj.lifetime_seconds, 0, 86400)
            self._bind_int("Collision cooldown ms", "collision_cooldown_ms", obj.collision_cooldown_ms, 0, 10000)
        elif isinstance(obj, WallObject):
            self._bind_double("Thickness", "thickness", obj.thickness, 1, 1000)
            self._bind_double("Bounciness", "restitution", obj.restitution, 0, 2, 3, 0.02)
            self._bind_double("Friction", "friction", obj.friction, 0, 5, 3, 0.02)
            self._bind_check("Break on hit", "break_on_hit", obj.break_on_hit)
            self._bind_double("Break strength", "break_strength", obj.break_strength, 0, 100000)
        elif isinstance(obj, RingObject):
            self._bind_double("Radius", "radius", obj.radius, 4, 5000)
            self._bind_double("Thickness", "thickness", obj.thickness, 1, 500)
            self._bind_double("Opening angle", "opening_angle", obj.opening_angle, 0, 359.9)
            self._bind_double("Opening rotation", "opening_rotation", obj.opening_rotation, -36000, 36000)
            self._bind_double("Rotation speed", "rotation_speed", obj.rotation_speed, -5000, 5000)
            self._bind_double("Expand/shrink speed", "expand_rate", obj.expand_rate, -5000, 5000)
            self._bind_double("Minimum radius", "minimum_radius", obj.minimum_radius, 1, 10000)
            self._bind_double("Maximum radius", "maximum_radius", obj.maximum_radius, 1, 10000)
            self._bind_int("Collision segments", "segments", obj.segments, 12, 720)
            self._bind_combo("Collision mode", "collision_mode", obj.collision_mode, [("Solid", "solid"), ("Trigger only", "trigger"), ("Disabled", "disabled")])
            self._bind_check("Break on hit", "break_on_hit", obj.break_on_hit)
            self._bind_double("Break strength", "break_strength", obj.break_strength, 0, 100000)
        elif isinstance(obj, BumperObject):
            self._bind_double("Radius", "radius", obj.radius, 2, 1000)
            self._bind_double("Bounciness", "restitution", obj.restitution, 0, 3)
            self._bind_double("Extra impulse", "impulse", obj.impulse, 0, 10000)
        elif isinstance(obj, PolygonObject):
            self._bind_double("Rotation speed", "rotation_speed", obj.rotation_speed, -5000, 5000)
            self._bind_double("Bounciness", "restitution", obj.restitution, 0, 2)
            self._bind_double("Friction", "friction", obj.friction, 0, 5)
            self._bind_check("Break on hit", "break_on_hit", obj.break_on_hit)
            self._bind_double("Break strength", "break_strength", obj.break_strength, 0, 100000)
        elif isinstance(obj, PortalObject):
            self._bind_double("Radius", "radius", obj.radius, 2, 1000)
            target = QComboBox()
            target.addItem("None", "")
            if self.project:
                for portal in [item for item in self.project.scene.objects if isinstance(item, PortalObject) and item.id != obj.id]:
                    target.addItem(portal.name, portal.id)
            target.setCurrentIndex(max(0, target.findData(obj.target_portal_id or "")))
            target.currentIndexChanged.connect(lambda: self._emit_object("target_portal_id", target.currentData() or None))
            self.object_layout.addRow("Target portal", target)
            self._bind_check("Preserve velocity", "preserve_velocity", obj.preserve_velocity)
            self._bind_double("Exit speed multiplier", "exit_speed_multiplier", obj.exit_speed_multiplier, 0, 10)
            self._bind_int("Cooldown ms", "cooldown_ms", obj.cooldown_ms, 0, 10000)
        elif isinstance(obj, EmitterObject):
            self._bind_check("Enabled", "enabled", obj.enabled)
            self._bind_vec2("Spawn area", "spawn_area", obj.spawn_area, 0, 10000, "W ", "H ")
            self._bind_double("Spawn interval", "spawn_interval", obj.spawn_interval, 0.01, 3600, 3, 0.1)
            self._bind_int("Initial ball count", "initial_ball_count", obj.initial_ball_count, 0, 10000)
            self._bind_int("Maximum ball count", "maximum_ball_count", obj.maximum_ball_count, 0, 100000)
            self._bind_vec2("Radius range", "radius_range", obj.radius_range, 1, 2000, "Min ", "Max ")
            self._bind_vec2("Speed range", "speed_range", obj.speed_range, 0, 50000, "Min ", "Max ")
            self._bind_vec2("Direction range", "direction_range", obj.direction_range, -36000, 36000, "Min° ", "Max° ")
            self._bind_vec2("Lifetime range", "lifetime_range", obj.lifetime_range, 0, 86400, "Min ", "Max ")
            self._bind_int("Random seed", "random_seed", obj.random_seed, -2147483648, 2147483647)
        elif isinstance(obj, TextOverlayObject):
            text = QPlainTextEdit(obj.text)
            text.setMaximumHeight(90)
            apply_text = QPushButton("Apply text")
            apply_text.clicked.connect(lambda: self._emit_object("text", text.toPlainText()))
            self.object_layout.addRow("Text", text)
            self.object_layout.addRow("", apply_text)
            self._bind_double("Font size", "font_size", obj.font_size, 4, 1000)
            self._bind_double("Opacity", "opacity", obj.opacity, 0, 1, 2, 0.05)

    def _project_section(self, text: str) -> None:
        label = QLabel(text)
        label.setStyleSheet("font-weight:700; color:#C7D2FE; margin-top:10px;")
        self.project_layout.addRow(label)

    def _project_int(self, label: str, path: str, value: int, minimum: int, maximum: int, optional: bool = False) -> QSpinBox:
        widget = self._integer(-1 if optional and value is None else value, minimum, maximum)
        if optional:
            widget.setSpecialValueText("Automatic")
        widget.editingFinished.connect(
            lambda p=path, w=widget, opt=optional: self.project_property_changed.emit(p, None if opt and w.value() < 0 else w.value())
        )
        self.project_layout.addRow(label, widget)
        self._project_bindings[path] = (widget, "optional_int" if optional else "int")
        return widget

    def _project_double(self, label: str, path: str, value: float, minimum: float, maximum: float, decimals: int = 2, step: float = 0.1) -> QDoubleSpinBox:
        widget = self._double(value, minimum, maximum, decimals, step)
        widget.editingFinished.connect(lambda p=path, w=widget: self.project_property_changed.emit(p, w.value()))
        self.project_layout.addRow(label, widget)
        self._project_bindings[path] = (widget, "double")
        return widget

    def _project_check(self, label: str, path: str, value: bool) -> QCheckBox:
        widget = QCheckBox()
        widget.setChecked(value)
        widget.toggled.connect(lambda checked, p=path: self.project_property_changed.emit(p, checked))
        self.project_layout.addRow(label, widget)
        self._project_bindings[path] = (widget, "check")
        return widget

    def _project_combo(self, label: str, path: str, value: str, values: list[tuple[str, str]]) -> QComboBox:
        widget = QComboBox()
        for display, data in values:
            widget.addItem(display, data)
        widget.setCurrentIndex(max(0, widget.findData(value)))
        widget.currentIndexChanged.connect(lambda _index, p=path, w=widget: self.project_property_changed.emit(p, w.currentData()))
        self.project_layout.addRow(label, widget)
        self._project_bindings[path] = (widget, "combo")
        return widget

    def _project_text(self, label: str, path: str, value: str) -> QLineEdit:
        widget = QLineEdit(value)
        widget.editingFinished.connect(lambda p=path, w=widget: self.project_property_changed.emit(p, w.text().strip()))
        self.project_layout.addRow(label, widget)
        self._project_bindings[path] = (widget, "text")
        return widget

    @staticmethod
    def _path_value(root, path: str):
        value = root
        for part in path.split("."):
            value = getattr(value, part)
        return value

    def _build_project_tab(self) -> None:
        self._project_bindings.clear()
        self._project_section("Color and output")
        self.palette_edit = QPlainTextEdit()
        self.palette_edit.setPlaceholderText("#FF4D6D, #FFD166, #06D6A0, #118AB2, #8338EC")
        self.palette_edit.setMaximumHeight(100)
        self.palette_apply = QPushButton("Apply palette")
        self.palette_feedback = QLabel()
        self.palette_feedback.setWordWrap(True)
        self.palette_apply.clicked.connect(self._apply_palette)
        self.project_layout.addRow("Color list", self.palette_edit)
        self.project_layout.addRow("", self.palette_apply)
        self.project_layout.addRow("", self.palette_feedback)
        self._project_combo("Palette mode", "scene.palette.mode", ColorMode.CYCLE.value, [(item.value.replace("_", " ").title(), item.value) for item in ColorMode])
        self._project_text("Background color", "render.background_color", "#0B1020")
        self._project_check("Transparent output", "render.transparent", False)
        self._project_check("Show grid", "render.show_grid", False)
        self._project_check("Show safe area", "render.show_safe_area", False)
        self._project_combo("Preview quality", "render.preview_quality", "high", [("Low", "low"), ("Medium", "medium"), ("High", "high")])

        self._project_section("MIDI playback")
        self.mapping_combo = QComboBox()
        for mode in MidiMappingMode:
            self.mapping_combo.addItem(mode.value.replace("_", " ").title(), mode.value)
        self.mapping_combo.currentIndexChanged.connect(lambda: self.project_property_changed.emit("midi_playback.mapping_mode", self.mapping_combo.currentData()))
        self.project_layout.addRow("MIDI mapping", self.mapping_combo)
        self.chord_window = self._integer(35, 0, 2000)
        self.chord_window.editingFinished.connect(lambda: self.project_property_changed.emit("midi_playback.chord_window_ms", self.chord_window.value()))
        self.project_layout.addRow("Chord window ms", self.chord_window)
        self.tempo = self._double(1, 0.05, 8, 2, 0.05)
        self.tempo.editingFinished.connect(lambda: self.project_property_changed.emit("midi_playback.tempo_multiplier", self.tempo.value()))
        self.project_layout.addRow("Tempo multiplier", self.tempo)
        self.transpose = self._integer(0, -48, 48)
        self.transpose.editingFinished.connect(lambda: self.project_property_changed.emit("midi_playback.transpose", self.transpose.value()))
        self.project_layout.addRow("Transpose", self.transpose)
        self.global_cooldown = self._integer(80, 0, 10000)
        self.global_cooldown.editingFinished.connect(lambda: self.project_property_changed.emit("midi_playback.collision_cooldown_ms", self.global_cooldown.value()))
        self.project_layout.addRow("Collision cooldown ms", self.global_cooldown)
        self._project_int("Octave shift", "midi_playback.octave_shift", 0, -8, 8)
        self._project_double("Velocity multiplier", "midi_playback.velocity_multiplier", 1.0, 0.0, 4.0, 2, 0.05)
        self._project_int("Minimum velocity", "midi_playback.minimum_velocity", 1, 1, 127)
        self._project_int("Maximum velocity", "midi_playback.maximum_velocity", 127, 1, 127)
        self._project_int("Note duration ms", "midi_playback.note_duration_ms", 180, 10, 60000)
        self._project_check("Sustain original duration", "midi_playback.sustain", False)
        self._project_check("Loop tracks", "midi_playback.loop", True)
        self._project_check("Restart tracks on restart", "midi_playback.restart_on_simulation_restart", True)
        self._project_check("Continue previous note position", "midi_playback.continue_position", False)
        self._project_check("Reverse note order", "midi_playback.reverse_order", False)
        self._project_check("Shuffle note order", "midi_playback.shuffle_order", False)
        self._project_combo("Quantization", "midi_playback.quantization", "off", [("Off", "off"), ("1/4", "1/4"), ("1/8", "1/8"), ("1/16", "1/16"), ("1/32", "1/32")])
        self._project_combo("Scale filter", "midi_playback.scale_filter", "chromatic", [("Chromatic", "chromatic"), ("Major", "major"), ("Minor", "minor"), ("Pentatonic", "pentatonic")])
        self._project_int("Instrument override", "midi_playback.instrument_override", -1, -1, 127, optional=True)
        self._project_int("Channel override", "midi_playback.channel_override", -1, -1, 15, optional=True)
        self._project_int("Polyphony limit", "midi_playback.polyphony_limit", 64, 1, 1024)
        self._project_check("Strength → velocity", "midi_playback.strength_controls_velocity", True)
        self._project_check("Strength → volume", "midi_playback.strength_controls_volume", False)
        self._project_check("Strength → duration", "midi_playback.strength_controls_duration", False)
        self._project_check("Strength → pitch", "midi_playback.strength_controls_pitch", False)
        self._project_check("Strength → particles", "midi_playback.strength_controls_particles", True)
        self._project_check("Strength → glow", "midi_playback.strength_controls_glow", True)
        self._project_check("Strength → ball size", "midi_playback.strength_controls_size", False)
        self._project_check("Strength → camera shake", "midi_playback.strength_controls_camera_shake", False)

        self._project_section("Resolution and recording")
        self.resolution_preset = QComboBox()
        for label, size in [
            ("Custom", None), ("720 × 1280", (720, 1280)), ("1080 × 1920", (1080, 1920)),
            ("1440 × 2560", (1440, 2560)), ("1080 × 1080 (1:1)", (1080, 1080)),
            ("1080 × 1350 (4:5)", (1080, 1350)), ("1080 × 1440 (3:4)", (1080, 1440)),
            ("1920 × 1080", (1920, 1080)), ("2560 × 1440", (2560, 1440)), ("3840 × 2160", (3840, 2160)),
        ]:
            self.resolution_preset.addItem(label, size)
        self.resolution_preset.currentIndexChanged.connect(self._resolution_selected)
        self.project_layout.addRow("Resolution preset", self.resolution_preset)
        res_row = QHBoxLayout()
        self.width_spin = self._integer(1080, 64, 16384)
        self.height_spin = self._integer(1920, 64, 16384)
        self.width_spin.setPrefix("W ")
        self.height_spin.setPrefix("H ")
        res_row.addWidget(self.width_spin)
        res_row.addWidget(self.height_spin)
        self.width_spin.editingFinished.connect(lambda: self.project_property_changed.emit("render.width", self.width_spin.value()))
        self.height_spin.editingFinished.connect(lambda: self.project_property_changed.emit("render.height", self.height_spin.value()))
        self.project_layout.addRow("Custom size", res_row)
        self.fps_spin = self._integer(60, 1, 240)
        self.fps_spin.editingFinished.connect(lambda: self.project_property_changed.emit("render.fps", self.fps_spin.value()))
        self.project_layout.addRow("Output FPS", self.fps_spin)
        self.preview_scale = self._double(0.5, 0.1, 1.0, 2, 0.1)
        self.preview_scale.editingFinished.connect(lambda: self.project_property_changed.emit("render.preview_scale", self.preview_scale.value()))
        self.project_layout.addRow("Preview scale", self.preview_scale)
        self.show_fps = QCheckBox()
        self.show_fps.toggled.connect(lambda value: self.project_property_changed.emit("render.show_fps", value))
        self.project_layout.addRow("Show FPS overlay", self.show_fps)
        self.duration = self._double(30, 0.1, 86400, 2, 1)
        self.duration.editingFinished.connect(lambda: self.project_property_changed.emit("recording.duration_seconds", self.duration.value()))
        self.project_layout.addRow("Recording duration", self.duration)
        self.seed = self._integer(1337, -2147483648, 2147483647)
        self.seed.editingFinished.connect(lambda: self.project_property_changed.emit("scene.physics.deterministic_seed", self.seed.value()))
        self.project_layout.addRow("Random seed", self.seed)
        self.physics_hz = self._integer(120, 15, 1000)
        self.physics_hz.editingFinished.connect(lambda: self.project_property_changed.emit("scene.physics.physics_hz", self.physics_hz.value()))
        self.project_layout.addRow("Physics updates/sec", self.physics_hz)
        self.max_balls = self._integer(500, 1, 100000)
        self.max_balls.editingFinished.connect(lambda: self.project_property_changed.emit("scene.physics.max_balls", self.max_balls.value()))
        self.project_layout.addRow("Maximum balls", self.max_balls)

        self._project_section("Global physics")
        gravity_row = QHBoxLayout()
        self.gravity_x = self._double(0.0, -10000, 10000, 2, 10)
        self.gravity_y = self._double(900.0, -10000, 10000, 2, 10)
        self.gravity_x.setPrefix("X "); self.gravity_y.setPrefix("Y ")
        gravity_row.addWidget(self.gravity_x); gravity_row.addWidget(self.gravity_y)
        emit_gravity = lambda: self.project_property_changed.emit("scene.physics.gravity", (self.gravity_x.value(), self.gravity_y.value()))
        self.gravity_x.editingFinished.connect(emit_gravity); self.gravity_y.editingFinished.connect(emit_gravity)
        self.project_layout.addRow("Gravity", gravity_row)
        self._project_double("Air resistance", "scene.physics.air_resistance", 0.995, 0.0, 1.0, 4, 0.001)
        self._project_double("Simulation speed", "scene.physics.simulation_speed", 1.0, 0.01, 20.0, 3, 0.1)
        self._project_int("Physics substeps", "scene.physics.substeps", 1, 1, 32)
        self._project_check("Automatic anti-tunneling", "scene.physics.continuous_collision_detection", True)
        self._project_int("Maximum collision substeps", "scene.physics.max_collision_substeps", 16, 1, 64)
        self._project_double("Collision skin", "scene.physics.collision_skin", 1.5, 0.0, 20.0, 2, 0.1)
        self._project_int("Collision iterations", "scene.physics.collision_iterations", 16, 1, 100)
        self._project_double("Global friction", "scene.physics.global_friction", 0.5, 0.0, 5.0, 3, 0.05)
        self._project_double("Global restitution", "scene.physics.global_restitution", 0.92, 0.0, 2.0, 3, 0.02)
        self._project_double("Global maximum speed", "scene.physics.maximum_speed", 2500, 0, 100000, 1, 50)
        self._project_check("World boundaries", "scene.physics.world_boundaries", True)
        self._project_check("Wraparound", "scene.physics.wraparound", False)
        self._project_int("Maximum particles", "scene.physics.max_particles", 8000, 0, 1000000)

        self._project_section("Camera")
        self._project_combo("Camera mode", "camera.mode", CameraMode.STATIC.value, [(item.value.replace("_", " ").title(), item.value) for item in CameraMode])
        camera_pan_row = QHBoxLayout()
        self.camera_pan_x = self._double(0.0, -100000, 100000, 2, 10)
        self.camera_pan_y = self._double(0.0, -100000, 100000, 2, 10)
        self.camera_pan_x.setPrefix("X "); self.camera_pan_y.setPrefix("Y ")
        camera_pan_row.addWidget(self.camera_pan_x); camera_pan_row.addWidget(self.camera_pan_y)
        emit_camera_pan = lambda: self.project_property_changed.emit("camera.pan", (self.camera_pan_x.value(), self.camera_pan_y.value()))
        self.camera_pan_x.editingFinished.connect(emit_camera_pan); self.camera_pan_y.editingFinished.connect(emit_camera_pan)
        self.project_layout.addRow("Camera pan", camera_pan_row)
        self._project_double("Camera zoom", "camera.zoom", 1.0, 0.05, 20.0, 3, 0.05)
        self._project_double("Camera smoothing", "camera.smoothing", 0.12, 0.0, 1.0, 3, 0.02)
        self._project_double("Camera shake intensity", "camera.shake_intensity", 0.0, 0.0, 10.0, 2, 0.1)
        self._project_combo("Framing", "camera.framing", "portrait", [("Portrait", "portrait"), ("Landscape", "landscape"), ("Square", "square")])

        self._project_section("Project audio")
        self._project_double("Master volume", "audio.master_volume", 0.8, 0.0, 1.0, 2, 0.05)
        self._project_int("Sample rate", "audio.sample_rate", 48000, 8000, 192000)
        self._project_int("Buffer size", "audio.buffer_size", 512, 64, 8192)
        self._project_int("Latency ms", "audio.latency_ms", 30, 5, 500)
        self._project_combo("Fallback waveform", "audio.fallback_waveform", Waveform.SINE.value, [(item.value.title(), item.value) for item in Waveform])

    def _sync_project_tab(self) -> None:
        if not self.project:
            return
        p = self.project
        widgets = [self.mapping_combo, self.chord_window, self.tempo, self.transpose, self.global_cooldown,
                   self.width_spin, self.height_spin, self.fps_spin, self.preview_scale, self.show_fps,
                   self.duration, self.seed, self.physics_hz, self.max_balls, self.palette_edit, self.gravity_x, self.gravity_y,
                   self.camera_pan_x, self.camera_pan_y]
        for widget in widgets:
            widget.blockSignals(True)
        self.palette_edit.setPlainText(", ".join(p.scene.palette.colors))
        self.mapping_combo.setCurrentIndex(max(0, self.mapping_combo.findData(p.midi_playback.mapping_mode.value)))
        self.chord_window.setValue(p.midi_playback.chord_window_ms)
        self.tempo.setValue(p.midi_playback.tempo_multiplier)
        self.transpose.setValue(p.midi_playback.transpose)
        self.global_cooldown.setValue(p.midi_playback.collision_cooldown_ms)
        self.width_spin.setValue(p.render.width)
        self.height_spin.setValue(p.render.height)
        self.fps_spin.setValue(p.render.fps)
        self.preview_scale.setValue(p.render.preview_scale)
        self.show_fps.setChecked(p.render.show_fps)
        self.duration.setValue(p.recording.duration_seconds)
        self.seed.setValue(p.scene.physics.deterministic_seed)
        self.physics_hz.setValue(p.scene.physics.physics_hz)
        self.max_balls.setValue(p.scene.physics.max_balls)
        self.gravity_x.setValue(p.scene.physics.gravity[0])
        self.gravity_y.setValue(p.scene.physics.gravity[1])
        self.camera_pan_x.setValue(p.camera.pan[0])
        self.camera_pan_y.setValue(p.camera.pan[1])
        for path, (widget, kind) in self._project_bindings.items():
            widget.blockSignals(True)
            value = self._path_value(p, path)
            if hasattr(value, "value"):
                value = value.value
            if kind == "combo":
                widget.setCurrentIndex(max(0, widget.findData(value)))
            elif kind == "check":
                widget.setChecked(bool(value))
            elif kind == "optional_int":
                widget.setValue(-1 if value is None else int(value))
            elif kind == "int":
                widget.setValue(int(value))
            elif kind == "double":
                widget.setValue(float(value))
            elif kind == "text":
                widget.setText(str(value))
            widget.blockSignals(False)
        for widget in widgets:
            widget.blockSignals(False)

    def _apply_palette(self) -> None:
        try:
            colors = parse_color_list(self.palette_edit.toPlainText())
        except ColorParseError as exc:
            self.palette_feedback.setText(str(exc))
            self.palette_feedback.setStyleSheet("color:#F87171")
            return
        self.palette_feedback.setText(f"Applied {len(colors)} color{'s' if len(colors) != 1 else ''}.")
        self.palette_feedback.setStyleSheet("color:#34D399")
        self.project_property_changed.emit("scene.palette.colors", colors)

    def _resolution_selected(self) -> None:
        size = self.resolution_preset.currentData()
        if not size:
            return
        width, height = size
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)
        self.project_property_changed.emit("render.width", width)
        self.project_property_changed.emit("render.height", height)
