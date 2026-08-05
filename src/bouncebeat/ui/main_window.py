from __future__ import annotations

import copy
import json
import logging
import math
import time
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStyle,
    QToolBar,
)

from bouncebeat.audio.engine import AudioEngine
from bouncebeat.commands.project_commands import ProjectSnapshotCommand
from bouncebeat.config.settings import SettingsStore
from bouncebeat.midi.parser import MidiParseError, inspect_midi
from bouncebeat.models.enums import ObjectKind
from bouncebeat.models.events import NoteEvent, PhysicsEvent
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.models.scene import (
    BallObject,
    BumperObject,
    EmitterObject,
    ParticleSystemObject,
    PolygonObject,
    PortalObject,
    RingObject,
    TextOverlayObject,
    WallObject,
)
from bouncebeat.presets.builtin import PRESET_NAMES, assign_auto_tracks, create_preset
from bouncebeat.projects.recovery import clear_recovery, load_recovery, recovery_available, write_recovery
from bouncebeat.projects.serializer import ProjectFormatError, load_project, save_project
from bouncebeat.simulation.engine import SimulationEngine
from bouncebeat.utilities.ffmpeg import detect_ffmpeg
from bouncebeat.utilities.paths import log_dir

from .midi_dialog import MidiInspectorDialog
from .preview import PreviewWidget
from .properties import PropertiesPanel
from .render_dialog import RenderDialog
from .scene_tree import SceneTreePanel
from .settings_dialog import DEFAULT_SHORTCUTS, SettingsDialog
from .timeline import TimelineWidget
from .welcome import WelcomeDialog

logger = logging.getLogger("bouncebeat.ui.main")


class MainWindow(QMainWindow):
    def __init__(self, initial_project: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BounceBeat Studio")
        self.resize(1500, 920)
        self.setAcceptDrops(True)
        self.settings_store = SettingsStore()
        self.app_settings = self.settings_store.load()
        self.ffmpeg = detect_ffmpeg(self.app_settings.ffmpeg_path)
        self.shortcuts = {
            key: str(self.settings_store.qsettings.value(f"shortcuts/{key}", value))
            for key, value in DEFAULT_SHORTCUTS.items()
        }
        self.undo_stack = QUndoStack(self)
        self.project = create_preset("Classic Bounce")
        self.project.audio.soundfont_path = self.app_settings.soundfont_path
        self.project.audio.master_volume = self.app_settings.master_volume
        self.project.audio.sample_rate = self.app_settings.sample_rate
        self.project.audio.buffer_size = self.app_settings.buffer_size
        self.project.audio.audio_device = self.app_settings.audio_device
        self.project.audio.latency_ms = self.app_settings.latency_ms
        self.current_path = ""
        self.dirty = False
        self.selected_id: str | None = next((obj.id for obj in self.project.scene.objects if isinstance(obj, BallObject)), None)
        self.actual_fps = 0.0
        self._tick_frames = 0
        self._fps_started = time.perf_counter()
        self._last_tick = time.perf_counter()
        self._accumulator = 0.0
        self._fullscreen = False
        self._fullscreen_docks: list[tuple[QDockWidget, bool]] = []
        self._preview_move_before: dict[str, tuple[float, float]] = {}

        self._build_ui()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._connect_ui()
        self.audio = self._make_audio_engine(self.project.audio)
        self.engine = SimulationEngine(self.project, note_callback=self.audio.play, event_callback=self._physics_event)
        self._sync_all()

        self.simulation_timer = QTimer(self)
        self.simulation_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.simulation_timer.setInterval(8)
        self.simulation_timer.timeout.connect(self._tick)
        self.simulation_timer.start()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave)
        self._restart_autosave_timer()

        geometry = self.settings_store.qsettings.value("window/geometry")
        state = self.settings_store.qsettings.value("window/state")
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)

        if initial_project:
            QTimer.singleShot(0, lambda: self.open_project(initial_project))
        else:
            QTimer.singleShot(100, self._startup_prompts)

    def _make_audio_engine(self, settings) -> AudioEngine:
        audio = AudioEngine(settings, self)
        self.audio = audio
        audio.status_changed.connect(self._audio_status)
        audio.error.connect(lambda message: self.statusBar().showMessage(message, 8000))
        audio.start()
        return audio

    def _restart_audio_engine(self) -> None:
        was_playing = getattr(self, "engine", None) and self.engine.playing
        if hasattr(self, "audio"):
            self.audio.stop()
            self.audio.deleteLater()
        self.audio = self._make_audio_engine(self.project.audio)
        self.engine = SimulationEngine(self.project, note_callback=self.audio.play, event_callback=self._physics_event)
        self.engine.playing = bool(was_playing)
        self._accumulator = 0.0


    def _build_ui(self) -> None:
        self.preview = PreviewWidget()
        self.setCentralWidget(self.preview)
        self.scene_panel = SceneTreePanel()
        self.properties_panel = PropertiesPanel()
        self.timeline = TimelineWidget()
        self.scene_dock = QDockWidget("Scene", self)
        self.scene_dock.setObjectName("SceneDock")
        self.scene_dock.setWidget(self.scene_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.scene_dock)
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setWidget(self.properties_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.timeline_dock = QDockWidget("Timeline and events", self)
        self.timeline_dock.setObjectName("TimelineDock")
        self.timeline_dock.setWidget(self.timeline)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.timeline_dock)
        self.resizeDocks([self.scene_dock, self.properties_dock], [280, 370], Qt.Orientation.Horizontal)
        self.resizeDocks([self.timeline_dock], [210], Qt.Orientation.Vertical)
        self.status_fps = QLabel()
        self.status_objects = QLabel()
        self.status_audio = QLabel("Audio: starting…")
        self.status_view = QLabel(f"View {self.preview.view_zoom * 100:.0f}%")
        self.status_ffmpeg = QLabel("FFmpeg: ready" if self.ffmpeg.available else "FFmpeg: missing")
        self.statusBar().addPermanentWidget(self.status_fps)
        self.statusBar().addPermanentWidget(self.status_objects)
        self.statusBar().addPermanentWidget(self.status_view)
        self.statusBar().addPermanentWidget(self.status_audio)
        self.statusBar().addPermanentWidget(self.status_ffmpeg)

    def _action(self, text: str, slot, shortcut_key: str | None = None, checkable: bool = False) -> QAction:
        action = QAction(text, self)
        action.setCheckable(checkable)
        if shortcut_key:
            action.setShortcut(QKeySequence(self.shortcuts.get(shortcut_key, DEFAULT_SHORTCUTS.get(shortcut_key, ""))))
        action.triggered.connect(slot)
        return action

    def _build_actions(self) -> None:
        style = self.style()
        self.action_new = self._action("New Project", self.new_project)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_open = self._action("Open Project…", lambda: self.open_project(), "open")
        self.action_import_midi = self._action("Import MIDI…", self.import_midi)
        self.action_midi_inspector = self._action("MIDI Track Inspector…", self.open_midi_inspector)
        self.action_save = self._action("Save", self.save, "save")
        self.action_save_as = self._action("Save As…", self.save_as, "save_as")
        self.action_import_preset = self._action("Import Preset…", self.import_preset)
        self.action_export_preset = self._action("Export Preset…", self.export_preset)
        self.action_exit = self._action("Exit", self.close)
        self.action_undo = self.undo_stack.createUndoAction(self, "Undo")
        self.action_undo.setShortcut(QKeySequence(self.shortcuts["undo"]))
        self.action_redo = self.undo_stack.createRedoAction(self, "Redo")
        self.action_redo.setShortcut(QKeySequence(self.shortcuts["redo"]))
        self.action_copy = self._action("Copy", self.copy_selected)
        self.action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.action_paste = self._action("Paste", self.paste_object)
        self.action_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.action_duplicate = self._action("Duplicate", self.duplicate_selected, "duplicate")
        self.action_delete = self._action("Delete", self.delete_selected, "delete")
        self.action_play = self._action("Play / Pause", self.toggle_play, "play_pause")
        self.action_restart = self._action("Restart", self.restart_simulation, "restart")
        self.action_stop = self._action("Stop", self.stop_simulation)
        self.action_step = self._action("Step One Frame", self.step_frame, "step")
        self.action_record = self._action("Record / Render…", self.open_render_dialog, "record")
        self.action_fullscreen = self._action("Fullscreen Preview", self.toggle_fullscreen, "fullscreen")
        self.action_zoom_in = self._action("Zoom In", lambda: self._zoom_preview(1.2))
        self.action_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.action_zoom_out = self._action("Zoom Out", lambda: self._zoom_preview(1 / 1.2))
        self.action_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.action_fit_canvas = self._action("Fit Entire Canvas", self._fit_preview)
        self.action_fit_canvas.setShortcut(QKeySequence("Ctrl+0"))
        self.action_fit_width = self._action("Fit Canvas Width", self._fit_preview_width)
        self.action_actual_pixels = self._action("Actual Pixels (1:1)", self._actual_preview_pixels)
        self.action_actual_pixels.setShortcut(QKeySequence("Ctrl+1"))
        self.action_grid = self._action("Show Grid", self._toggle_grid, checkable=True)
        self.action_safe = self._action("Show Safe-Area Guides", self._toggle_safe_area, checkable=True)
        self.action_fps = self._action("Show FPS Overlay", self._toggle_fps, checkable=True)
        self.action_fps.setChecked(self.project.render.show_fps)
        self.action_panic = self._action("Audio Panic", self.audio_panic)
        self.action_settings = self._action("Settings…", self.open_settings)
        self.action_welcome = self._action("Welcome / Tutorial", self.show_welcome)
        self.action_about = self._action("About BounceBeat Studio", self.show_about)
        self.action_logs = self._action("Open Log Folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir()))))
        self.action_play.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.action_stop.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.action_restart.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.action_record.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.action_save.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.action_open.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.escape_action = QAction(self)
        self.escape_action.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        self.escape_action.triggered.connect(self._escape)
        self.addAction(self.escape_action)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addActions([self.action_new, self.action_open, self.action_import_midi, self.action_midi_inspector])
        self.recent_projects_menu = file_menu.addMenu("Recent Projects")
        self.recent_midi_menu = file_menu.addMenu("Recent MIDI")
        file_menu.addSeparator()
        file_menu.addActions([self.action_save, self.action_save_as])
        file_menu.addSeparator()
        file_menu.addActions([self.action_import_preset, self.action_export_preset])
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)
        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addActions([self.action_undo, self.action_redo])
        edit_menu.addSeparator()
        edit_menu.addActions([self.action_copy, self.action_paste, self.action_duplicate, self.action_delete])
        scene_menu = self.menuBar().addMenu("&Scene")
        add_menu = scene_menu.addMenu("Add Object")
        for kind, label in [
            (ObjectKind.BALL, "Ball"), (ObjectKind.WALL, "Wall"), (ObjectKind.RING, "Ring"),
            (ObjectKind.BUMPER, "Bumper"), (ObjectKind.POLYGON, "Rotating obstacle"),
            (ObjectKind.PORTAL, "Portal"), (ObjectKind.EMITTER, "Emitter"),
            (ObjectKind.TEXT, "Text overlay"), (ObjectKind.PARTICLE_SYSTEM, "Particle system"),
        ]:
            action = add_menu.addAction(label)
            action.triggered.connect(lambda checked=False, value=kind.value: self.add_object(value))
        presets_menu = scene_menu.addMenu("Presets")
        for name in PRESET_NAMES:
            action = presets_menu.addAction(name)
            action.triggered.connect(lambda checked=False, value=name: self.load_preset(value))
        playback = self.menuBar().addMenu("&Playback")
        playback.addActions([self.action_play, self.action_stop, self.action_restart, self.action_step])
        playback.addSeparator()
        playback.addActions([
            self.action_zoom_in, self.action_zoom_out, self.action_fit_canvas,
            self.action_fit_width, self.action_actual_pixels,
        ])
        playback.addSeparator()
        playback.addActions([self.action_grid, self.action_safe, self.action_fps, self.action_fullscreen])
        recording = self.menuBar().addMenu("&Recording")
        recording.addAction(self.action_record)
        tools = self.menuBar().addMenu("&Tools")
        tools.addActions([self.action_midi_inspector, self.action_panic, self.action_settings, self.action_logs])
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addActions([self.action_welcome, self.action_about])
        self._refresh_recent_menus()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Transport", self)
        toolbar.setObjectName("TransportToolbar")
        toolbar.setMovable(True)
        toolbar.addAction(self.action_play)
        toolbar.addAction(self.action_stop)
        toolbar.addAction(self.action_restart)
        toolbar.addAction(self.action_step)
        toolbar.addSeparator()
        toolbar.addAction(self.action_record)
        toolbar.addSeparator()
        toolbar.addAction(self.action_import_midi)
        toolbar.addAction(self.action_save)
        toolbar.addSeparator()
        toolbar.addAction(self.action_grid)
        toolbar.addAction(self.action_safe)
        toolbar.addAction(self.action_fps)
        toolbar.addSeparator()
        toolbar.addAction(self.action_zoom_out)
        toolbar.addAction(self.action_zoom_in)
        toolbar.addAction(self.action_fit_canvas)
        toolbar.addAction(self.action_fit_width)
        self.addToolBar(toolbar)
        self.transport_toolbar = toolbar

    def _connect_ui(self) -> None:
        self.preview.object_selected.connect(self.select_object)
        self.preview.object_moved.connect(self._move_object_from_preview)
        self.preview.zoom_requested.connect(self._zoom_preview)
        self.preview.view_changed.connect(self._update_view_status)
        self.preview.play_pause_requested.connect(self.toggle_play)
        self.scene_panel.selected.connect(self.select_object)
        self.scene_panel.add_requested.connect(self.add_object)
        self.scene_panel.duplicate_requested.connect(lambda object_id: self.duplicate_object(object_id))
        self.scene_panel.delete_requested.connect(lambda object_id: self.delete_object(object_id))
        self.scene_panel.visibility_changed.connect(lambda object_id, value: self.change_object_property(object_id, "visible", value))
        self.scene_panel.lock_changed.connect(lambda object_id, value: self.change_object_property(object_id, "locked", value))
        self.scene_panel.reordered.connect(self.reorder_objects)
        self.scene_panel.group_requested.connect(self.group_objects)
        self.properties_panel.object_property_changed.connect(self.change_object_property)
        self.properties_panel.project_property_changed.connect(self.change_project_property)


    def _startup_prompts(self) -> None:
        if recovery_available():
            answer = QMessageBox.question(
                self, "Recover autosaved project?",
                "BounceBeat Studio found an autosave from a previous session. Open it?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    self._install_project(load_recovery(), mark_dirty=True, clear_undo=True)
                    return
                except Exception as exc:
                    logger.exception("Recovery failed")
                    QMessageBox.warning(self, "Recovery failed", str(exc))
        if not self.settings_store.qsettings.value("ui/welcome_seen", False, bool):
            self.show_welcome()
            self.settings_store.qsettings.setValue("ui/welcome_seen", True)

    def _maybe_save_changes(self) -> bool:
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self, "Unsaved changes",
            "Save changes to the current project?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return True

    def new_project(self) -> None:
        if not self._maybe_save_changes():
            return
        project = BounceBeatProject(name="Untitled Project")
        project.audio.soundfont_path = self.app_settings.soundfont_path
        project.audio.master_volume = self.app_settings.master_volume
        project.audio.sample_rate = self.app_settings.sample_rate
        project.audio.buffer_size = self.app_settings.buffer_size
        project.audio.audio_device = self.app_settings.audio_device
        project.audio.latency_ms = self.app_settings.latency_ms
        self._install_project(project, mark_dirty=False, clear_undo=True)

    def open_project(self, path: str = "") -> None:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open BounceBeat project", "", "BounceBeat projects (*.bouncebeat)")
        if not path:
            return
        if not self._maybe_save_changes():
            return
        try:
            project = load_project(path)
        except ProjectFormatError as exc:
            QMessageBox.critical(self, "Could not open project", str(exc))
            return
        missing = project.midi_asset.path and not Path(project.midi_asset.path).is_file()
        self._install_project(project, path, mark_dirty=False, clear_undo=True)
        self.settings_store.add_recent_project(path)
        self._refresh_recent_menus()
        if missing:
            QMessageBox.warning(
                self, "Missing MIDI asset",
                "The project opened, but its referenced MIDI file could not be found. Re-import the MIDI to restore playback.",
            )

    def save(self) -> bool:
        if not self.current_path:
            return self.save_as()
        try:
            save_project(self.project, self.current_path, self.project.embedded_midi)
            self.dirty = False
            clear_recovery()
            self._update_title()
            self.statusBar().showMessage("Project saved", 3000)
            return True
        except Exception as exc:
            logger.exception("Save failed")
            QMessageBox.critical(self, "Could not save project", str(exc))
            return False

    def save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save BounceBeat project", self.current_path or f"{self.project.name}.bouncebeat",
            "BounceBeat projects (*.bouncebeat)",
        )
        if not path:
            return False
        embed = QMessageBox.question(
            self, "Embed MIDI?",
            "Embed the imported MIDI inside the project file? This makes the project portable but slightly larger.",
        ) == QMessageBox.StandardButton.Yes
        try:
            saved = save_project(self.project, path, embed)
            self.current_path = str(saved)
            self.settings_store.add_recent_project(self.current_path)
            self._refresh_recent_menus()
            self.dirty = False
            clear_recovery()
            self._update_title()
            return True
        except Exception as exc:
            logger.exception("Save As failed")
            QMessageBox.critical(self, "Could not save project", str(exc))
            return False

    def export_preset(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export editable preset", f"{self.project.preset_name or self.project.name}.bbpreset",
            "BounceBeat presets (*.bbpreset);;JSON files (*.json)",
        )
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() not in {".bbpreset", ".json"}:
            target = target.with_suffix(".bbpreset")
        data = self.project.to_dict()
        data["midi_asset"] = {"path": "", "embedded_name": "", "ticks_per_beat": 480, "duration": 0.0, "tracks": []}
        data["selected_track_ids"] = []
        data["embedded_midi"] = False
        data["metadata"] = {**data.get("metadata", {}), "artifact_type": "bouncebeat_preset"}
        try:
            target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self.statusBar().showMessage(f"Preset exported to {target.name}", 4000)
        except OSError as exc:
            QMessageBox.critical(self, "Could not export preset", str(exc))

    def import_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import editable preset", "", "BounceBeat presets (*.bbpreset *.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            preset = BounceBeatProject.from_dict(data)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Could not import preset", str(exc))
            return
        current_midi = copy.deepcopy(self.project.midi_asset)
        current_tracks = list(self.project.selected_track_ids)
        current_audio = copy.deepcopy(self.project.audio)
        preset.midi_asset = current_midi
        preset.selected_track_ids = current_tracks
        preset.audio = current_audio
        assign_auto_tracks(preset)
        if current_tracks:
            for index, ball in enumerate(obj for obj in preset.scene.objects if isinstance(obj, BallObject)):
                if not ball.midi_track_ids:
                    ball.midi_track_ids = [current_tracks[index % len(current_tracks)]]
        self._install_project(preset, mark_dirty=True, clear_undo=True)
        self.statusBar().showMessage(f"Imported preset {Path(path).name}", 4000)

    def _install_project(
        self,
        project: BounceBeatProject,
        path: str = "",
        *,
        mark_dirty: bool,
        clear_undo: bool,
    ) -> None:
        self.audio.panic() if hasattr(self, "audio") else None
        self.project = project
        if path:
            self.current_path = path
        elif project.project_path:
            self.current_path = project.project_path
        else:
            self.current_path = ""
        if not project.audio.soundfont_path:
            project.audio.soundfont_path = self.app_settings.soundfont_path
        if hasattr(self, "audio"):
            self.audio.stop()
            self.audio.deleteLater()
            self.audio = self._make_audio_engine(project.audio)
        self.engine = SimulationEngine(project, note_callback=self.audio.play if hasattr(self, "audio") else None, event_callback=self._physics_event)
        self.selected_id = next((obj.id for obj in project.scene.objects if isinstance(obj, BallObject)), project.scene.objects[0].id if project.scene.objects else None)
        self.dirty = mark_dirty
        self._accumulator = 0.0
        if clear_undo:
            self.undo_stack.clear()
        self._sync_all()

    def _apply_snapshot(self, data: dict) -> None:
        path = self.current_path
        project = BounceBeatProject.from_dict(copy.deepcopy(data))
        project.project_path = path
        self._install_project(project, path, mark_dirty=True, clear_undo=False)

    def _mutate(self, text: str, callback) -> None:
        before = copy.deepcopy(self.project.to_dict())
        callback()
        after = copy.deepcopy(self.project.to_dict())
        if before == after:
            return
        self.undo_stack.push(ProjectSnapshotCommand(text, before, after, self._apply_snapshot, already_applied=True))
        self.dirty = True
        self._rebuild_engine()
        self._sync_all()

    def _rebuild_engine(self) -> None:
        was_playing = getattr(self, "engine", None) and self.engine.playing
        self.audio.panic()
        self.engine = SimulationEngine(self.project, note_callback=self.audio.play, event_callback=self._physics_event)
        self.engine.playing = bool(was_playing)
        self._accumulator = 0.0


    def import_midi(self, path: str = "") -> None:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Import MIDI", "", "MIDI files (*.mid *.midi)")
        if not path:
            return
        try:
            asset = inspect_midi(path)
        except MidiParseError as exc:
            QMessageBox.critical(self, "Invalid MIDI file", str(exc))
            return
        dialog = MidiInspectorDialog(asset, parent=self)
        dialog.preview_requested.connect(lambda track_id: self._preview_midi_track(asset, track_id))
        if dialog.exec() != MidiInspectorDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_track_ids()
        def apply() -> None:
            self.project.midi_asset = asset
            self.project.selected_track_ids = selected
            assign_auto_tracks(self.project)
            balls = [obj for obj in self.project.scene.objects if isinstance(obj, BallObject)]
            for index, ball in enumerate(balls):
                if not ball.midi_track_ids and selected:
                    ball.midi_track_ids = [selected[index % len(selected)]]
        self._mutate("Import MIDI", apply)
        self.settings_store.add_recent_midi(path)
        self._refresh_recent_menus()
        if not asset.playable_tracks():
            QMessageBox.warning(self, "No playable notes", "The MIDI file contains no playable note tracks.")
        else:
            self.statusBar().showMessage(f"Imported {len(asset.playable_tracks())} playable MIDI tracks", 5000)

    def open_midi_inspector(self) -> None:
        if not self.project.midi_asset.tracks:
            self.import_midi()
            return
        dialog = MidiInspectorDialog(self.project.midi_asset, self.project.selected_track_ids, self)
        dialog.preview_requested.connect(lambda track_id: self._preview_midi_track(self.project.midi_asset, track_id))
        if dialog.exec() == MidiInspectorDialog.DialogCode.Accepted:
            selected = dialog.selected_track_ids()
            self._mutate("Change MIDI track selection", lambda: setattr(self.project, "selected_track_ids", selected))

    def _preview_midi_track(self, asset, track_id: str) -> None:
        track = asset.get_track(track_id)
        if not track or not track.notes:
            return
        self.audio.panic()
        notes = track.notes[:24]
        base = notes[0].start
        for note in notes:
            delay = max(0, round((note.start - base) * 1000))
            event = NoteEvent(
                time=0, pitch=note.pitch, velocity=note.velocity, duration=max(0.08, min(1.5, note.duration)),
                track_id=track.id, channel=note.channel, program=note.program, pan=track.pan, volume=track.volume,
            )
            QTimer.singleShot(delay, lambda e=event: self.audio.play([e]))


    def load_preset(self, name: str) -> None:
        if not self._maybe_save_changes():
            return
        midi_asset = copy.deepcopy(self.project.midi_asset)
        selected = list(self.project.selected_track_ids)
        audio = copy.deepcopy(self.project.audio)
        project = create_preset(name)
        project.midi_asset = midi_asset
        project.selected_track_ids = selected
        project.audio = audio
        assign_auto_tracks(project)
        if selected:
            for index, ball in enumerate([obj for obj in project.scene.objects if isinstance(obj, BallObject)]):
                if not ball.midi_track_ids:
                    ball.midi_track_ids = [selected[index % len(selected)]]
        self._install_project(project, mark_dirty=True, clear_undo=True)

    def add_object(self, kind_value: str) -> None:
        kind = ObjectKind(kind_value)
        center = (self.project.scene.logical_width / 2, self.project.scene.logical_height / 2)
        if kind == ObjectKind.BALL:
            obj = BallObject(position=center, color=self.project.scene.palette.colors[0])
        elif kind == ObjectKind.WALL:
            obj = WallObject(position=center, start=(center[0] - 180, center[1]), end=(center[0] + 180, center[1]))
        elif kind == ObjectKind.RING:
            obj = RingObject(position=center, radius=220, opening_angle=35, color=self.project.scene.palette.ring)
        elif kind == ObjectKind.BUMPER:
            obj = BumperObject(position=center, color=self.project.scene.palette.colors[1 % len(self.project.scene.palette.colors)])
        elif kind == ObjectKind.POLYGON:
            obj = PolygonObject(position=center, rotation_speed=30, color=self.project.scene.palette.obstacle)
        elif kind == ObjectKind.PORTAL:
            obj = PortalObject(position=center, color=self.project.scene.palette.colors[-1])
        elif kind == ObjectKind.EMITTER:
            obj = EmitterObject(position=center, spawn_area=(180, 100), color=self.project.scene.palette.colors[2 % len(self.project.scene.palette.colors)])
        elif kind == ObjectKind.TEXT:
            obj = TextOverlayObject(position=(center[0], 160), color=self.project.scene.palette.text)
        else:
            obj = ParticleSystemObject(position=center)
        self._mutate(f"Add {obj.kind.value}", lambda: self.project.scene.add(obj))
        self.select_object(obj.id)

    def select_object(self, object_id: str) -> None:
        if self.project.scene.get(object_id) or object_id in self.engine.models:
            self.selected_id = object_id
            self.engine.set_selected_object(object_id)
            if self.project.camera.mode.value == "follow_selected":
                self.project.camera.follow_object_id = object_id
            self.scene_panel.set_scene(self.project.scene, self.selected_id)
            self.properties_panel.set_context(self.project, self.project.scene.get(object_id))
            self.preview.update()

    def duplicate_selected(self) -> None:
        if self.selected_id:
            self.duplicate_object(self.selected_id)

    def duplicate_object(self, object_id: str) -> None:
        holder: dict[str, str] = {}
        def apply() -> None:
            clone = self.project.scene.duplicate(object_id)
            if clone:
                holder["id"] = clone.id
        self._mutate("Duplicate object", apply)
        if holder.get("id"):
            self.select_object(holder["id"])

    def delete_selected(self) -> None:
        if self.selected_id:
            self.delete_object(self.selected_id)

    def delete_object(self, object_id: str) -> None:
        obj = self.project.scene.get(object_id)
        if not obj:
            return
        answer = QMessageBox.question(self, "Delete object?", f"Delete “{obj.name}”? This can be undone.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._mutate("Delete object", lambda: self.project.scene.remove(object_id))
        self.selected_id = self.project.scene.objects[0].id if self.project.scene.objects else None
        self._sync_all()

    def copy_selected(self) -> None:
        obj = self.project.scene.get(self.selected_id)
        if not obj:
            return
        from bouncebeat.models.scene import dataclass_to_dict
        QApplication.clipboard().setText("BOUNCEBEAT_OBJECT\n" + json.dumps(dataclass_to_dict(obj)))
        self.statusBar().showMessage("Object copied", 2000)

    def paste_object(self) -> None:
        text = QApplication.clipboard().text()
        if not text.startswith("BOUNCEBEAT_OBJECT\n"):
            QMessageBox.information(self, "Nothing to paste", "The clipboard does not contain a BounceBeat object.")
            return
        try:
            from bouncebeat.models.scene import object_from_dict, new_id
            data = json.loads(text.split("\n", 1)[1])
            obj = object_from_dict(data)
            obj.id = new_id(obj.kind.value)
            obj.name += " Copy"
            obj.position = (obj.position[0] + 30, obj.position[1] + 30)
        except Exception as exc:
            QMessageBox.warning(self, "Could not paste object", str(exc))
            return
        self._mutate("Paste object", lambda: self.project.scene.add(obj))
        self.select_object(obj.id)

    def group_objects(self, object_ids: list[str]) -> None:
        if not object_ids:
            return
        name, accepted = QInputDialog.getText(self, "Group objects", "Group name:")
        if not accepted or not name.strip():
            return
        def apply() -> None:
            for object_id in object_ids:
                obj = self.project.scene.get(object_id)
                if obj:
                    obj.group = name.strip()
        self._mutate("Group objects", apply)

    def reorder_objects(self, ids: list[str]) -> None:
        if not ids:
            return
        def apply() -> None:
            mapping = {obj.id: obj for obj in self.project.scene.objects}
            self.project.scene.objects = [mapping[object_id] for object_id in ids if object_id in mapping]
            self.project.scene._normalize_z_indexes()
        self._mutate("Reorder objects", apply)

    def change_object_property(self, object_id: str, name: str, value) -> None:
        obj = self.project.scene.get(object_id)
        if obj is None or not hasattr(obj, name):
            return
        def apply() -> None:
            current = getattr(obj, name)
            converted = value
            if isinstance(current, Enum):
                converted = type(current)(value)
            elif isinstance(current, tuple) and isinstance(value, (list, tuple)):
                converted = tuple(value)
            if isinstance(obj, WallObject) and name == "position":
                dx = converted[0] - obj.position[0]
                dy = converted[1] - obj.position[1]
                obj.start = (obj.start[0] + dx, obj.start[1] + dy)
                obj.end = (obj.end[0] + dx, obj.end[1] + dy)
            setattr(obj, name, converted)
        self._mutate(f"Change {name.replace('_', ' ')}", apply)

    def change_project_property(self, path: str, value) -> None:
        parts = path.split(".")
        def apply() -> None:
            target = self.project
            for part in parts[:-1]:
                target = getattr(target, part)
            attr = parts[-1]
            current = getattr(target, attr)
            converted = type(current)(value) if isinstance(current, Enum) else tuple(value) if isinstance(current, tuple) else value
            setattr(target, attr, converted)
        self._mutate(f"Change {parts[-1].replace('_', ' ')}", apply)
        if path.startswith("audio."):
            self._restart_audio_engine()

    def _move_object_from_preview(self, object_id: str, position: tuple[float, float]) -> None:
        obj = self.project.scene.get(object_id)
        if not obj or obj.locked:
            return
        if object_id not in self._preview_move_before:
            self._preview_move_before[object_id] = obj.position
        if isinstance(obj, WallObject):
            dx, dy = position[0] - obj.position[0], position[1] - obj.position[1]
            obj.start = (obj.start[0] + dx, obj.start[1] + dy)
            obj.end = (obj.end[0] + dx, obj.end[1] + dy)
        obj.position = position
        self.engine.set_object_position(object_id, position)
        self.dirty = True
        self.properties_panel.set_context(self.project, obj)
        self.scene_panel.set_scene(self.project.scene, object_id)


    def toggle_play(self) -> None:
        self.engine.playing = not self.engine.playing
        self.preview.simulation_playing = self.engine.playing
        self.action_play.setText("Pause" if self.engine.playing else "Play")
        self.statusBar().showMessage("Playing" if self.engine.playing else "Paused", 1200)
        self._last_tick = time.perf_counter()

    def stop_simulation(self) -> None:
        self.engine.playing = False
        self.audio.panic()
        self.engine.reset()
        self.preview.simulation_playing = False
        self.action_play.setText("Play / Pause")
        self._accumulator = 0.0
        self._sync_preview()

    def restart_simulation(self) -> None:
        playing = self.engine.playing
        self.audio.panic()
        self.engine.reset()
        self.engine.playing = playing
        self._accumulator = 0.0
        self._sync_preview()

    def step_frame(self) -> None:
        if self.engine.playing:
            self.engine.playing = False
        self.engine.step()
        self._sync_preview()

    def audio_panic(self) -> None:
        self.audio.panic()
        self.statusBar().showMessage("All notes stopped", 2000)

    def _tick(self) -> None:
        now = time.perf_counter()
        elapsed = min(0.25, max(0.0, now - self._last_tick))
        self._last_tick = now
        if self.engine.playing:
            self._accumulator += elapsed
            steps = 0
            while self._accumulator >= self.engine.fixed_dt and steps < 32:
                self.engine.step()
                self._accumulator -= self.engine.fixed_dt
                steps += 1
            if self._accumulator >= self.engine.fixed_dt:
                dropped = int(self._accumulator / self.engine.fixed_dt)
                self.engine._backend.dropped_frames += dropped
                self._accumulator %= self.engine.fixed_dt
        self._tick_frames += 1
        fps_elapsed = now - self._fps_started
        if fps_elapsed >= 0.5:
            self.actual_fps = self._tick_frames / fps_elapsed
            self._tick_frames = 0
            self._fps_started = now
        self._sync_preview()

    def _physics_event(self, event: PhysicsEvent) -> None:
        if len(self.engine.physics_events) % 20 == 0:
            self.timeline.set_data(self.project, self.engine.physics_events, self.engine.time)

    def _sync_preview(self) -> None:
        snapshot = self.engine.snapshot()
        self.preview.set_scene(self.project, snapshot, self.engine.models, self.selected_id, self.actual_fps)
        self.timeline.set_data(self.project, self.engine.physics_events, self.engine.time)
        self.status_fps.setText(f"FPS {self.actual_fps:.1f}/{self.project.render.fps}")
        self.status_objects.setText(f"Balls {snapshot.active_ball_count} • Collisions {snapshot.collision_count}")


    def _toggle_grid(self, checked: bool) -> None:
        self.project.render.show_grid = checked
        self.dirty = True
        self.preview.update()

    def _toggle_safe_area(self, checked: bool) -> None:
        self.project.render.show_safe_area = checked
        self.dirty = True
        self.preview.update()

    def _toggle_fps(self, checked: bool) -> None:
        self.project.render.show_fps = checked
        self.dirty = True
        self.properties_panel.set_context(self.project, self.project.scene.get(self.selected_id))
        self.preview.update()

    def _zoom_preview(self, factor: float) -> None:


        self.preview.zoom_by(factor)

    def _fit_preview(self) -> None:
        self.preview.fit_canvas()

    def _fit_preview_width(self) -> None:
        self.preview.fit_width()

    def _actual_preview_pixels(self) -> None:
        self.preview.actual_pixels()

    def _update_view_status(self, zoom: float) -> None:
        self.status_view.setText(f"View {zoom * 100:.0f}%")

    def toggle_fullscreen(self) -> None:
        if not self._fullscreen:
            self._fullscreen = True
            self._fullscreen_docks = [(dock, dock.isVisible()) for dock in (self.scene_dock, self.properties_dock, self.timeline_dock)]
            for dock, _ in self._fullscreen_docks:
                dock.hide()
            self.transport_toolbar.hide()
            self.menuBar().hide()
            self.statusBar().hide()
            self.showFullScreen()
        else:
            self._fullscreen = False
            self.showNormal()
            for dock, visible in self._fullscreen_docks:
                dock.setVisible(visible)
            self.transport_toolbar.show()
            self.menuBar().show()
            self.statusBar().show()

    def _escape(self) -> None:
        if self._fullscreen:
            self.toggle_fullscreen()
        elif self.engine.playing:
            self.engine.playing = False

    def open_render_dialog(self) -> None:
        self.engine.playing = False
        self.audio.panic()
        dialog = RenderDialog(self.project, self.ffmpeg, self)
        dialog.exec()
        self.dirty = True
        self._sync_all()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.app_settings, self.shortcuts, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        settings, shortcuts = dialog.values()
        self.app_settings = settings
        self.shortcuts = shortcuts
        self.settings_store.save(settings)
        for key, value in shortcuts.items():
            self.settings_store.qsettings.setValue(f"shortcuts/{key}", value)
        self.ffmpeg = detect_ffmpeg(settings.ffmpeg_path)
        self.project.audio.soundfont_path = settings.soundfont_path
        self.project.audio.master_volume = settings.master_volume
        self.project.audio.sample_rate = settings.sample_rate
        self.project.audio.buffer_size = settings.buffer_size
        self.project.audio.audio_device = settings.audio_device
        self.project.audio.latency_ms = settings.latency_ms
        self._restart_audio_engine()
        self._set_action_shortcuts()
        self._restart_autosave_timer()
        self.status_ffmpeg.setText("FFmpeg: ready" if self.ffmpeg.available else "FFmpeg: missing")
        self.dirty = True

    def _set_action_shortcuts(self) -> None:
        mapping = {
            "play_pause": self.action_play, "restart": self.action_restart, "record": self.action_record,
            "save": self.action_save, "save_as": self.action_save_as, "open": self.action_open,
            "undo": self.action_undo, "redo": self.action_redo, "delete": self.action_delete,
            "duplicate": self.action_duplicate, "fullscreen": self.action_fullscreen, "step": self.action_step,
        }
        for key, action in mapping.items():
            action.setShortcut(QKeySequence(self.shortcuts[key]))

    def _audio_status(self, message: str) -> None:
        self.status_audio.setText("Audio: " + self.audio.backend_name)
        self.statusBar().showMessage(message, 2500)

    def show_welcome(self) -> None:
        dialog = WelcomeDialog(self.ffmpeg, self.app_settings.soundfont_path, self)
        dialog.create_blank.connect(self.new_project)
        dialog.open_project.connect(lambda: self.open_project())
        dialog.import_midi.connect(lambda: self.import_midi())
        dialog.preset_requested.connect(self.load_preset)
        dialog.exec()

    def show_about(self) -> None:
        from bouncebeat import __version__
        QMessageBox.about(
            self, "About BounceBeat Studio",
            f"<h2>BounceBeat Studio {__version__}</h2>"
            "<p>A deterministic musical-physics editor with MIDI mapping, Pymunk simulation, "
            "built-in synthesis, SoundFont support, and direct FFmpeg rendering.</p>",
        )


    def _sync_all(self) -> None:
        self.scene_panel.set_scene(self.project.scene, self.selected_id)
        self.properties_panel.set_context(self.project, self.project.scene.get(self.selected_id))
        self.action_grid.setChecked(self.project.render.show_grid)
        self.action_safe.setChecked(self.project.render.show_safe_area)
        self.action_fps.setChecked(self.project.render.show_fps)
        self._sync_preview()
        self._update_title()

    def _update_title(self) -> None:
        marker = "*" if self.dirty else ""
        self.setWindowTitle(f"{self.project.name}{marker} — BounceBeat Studio")

    def _refresh_recent_menus(self) -> None:
        if not hasattr(self, "recent_projects_menu"):
            return
        self.recent_projects_menu.clear()
        for path in self.settings_store.recent_projects():
            action = self.recent_projects_menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(lambda checked=False, value=path: self.open_project(value))
        if not self.recent_projects_menu.actions():
            self.recent_projects_menu.addAction("No recent projects").setEnabled(False)
        self.recent_midi_menu.clear()
        for path in self.settings_store.recent_midi():
            action = self.recent_midi_menu.addAction(Path(path).name)
            action.setToolTip(path)
            action.triggered.connect(lambda checked=False, value=path: self.import_midi(value))
        if not self.recent_midi_menu.actions():
            self.recent_midi_menu.addAction("No recent MIDI files").setEnabled(False)

    def _restart_autosave_timer(self) -> None:
        if not hasattr(self, "autosave_timer"):
            return
        self.autosave_timer.stop()
        if self.app_settings.autosave_enabled:
            self.autosave_timer.start(max(15, self.app_settings.autosave_seconds) * 1000)

    def _autosave(self) -> None:
        if not self.dirty:
            return
        try:
            write_recovery(self.project)
            self.statusBar().showMessage("Autosaved recovery copy", 1500)
        except Exception:
            logger.exception("Autosave failed")


    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls and any(Path(url.toLocalFile()).suffix.lower() in {".mid", ".midi", ".bouncebeat"} for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            suffix = Path(path).suffix.lower()
            if suffix == ".bouncebeat":
                self.open_project(path)
                break
            if suffix in {".mid", ".midi"}:
                self.import_midi(path)
                break

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._maybe_save_changes():
            event.ignore()
            return
        self.audio.stop()
        self.settings_store.qsettings.setValue("window/geometry", self.saveGeometry())
        self.settings_store.qsettings.setValue("window/state", self.saveState())
        clear_recovery()
        event.accept()
