from __future__ import annotations

import os

import pytest

from bouncebeat.models.midi import MidiAsset
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.utilities.ffmpeg import FFmpegInfo


def test_top_level_qt_widgets_and_dialogs_construct():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from bouncebeat.config.settings import AppSettings
    from bouncebeat.ui.midi_dialog import MidiInspectorDialog
    from bouncebeat.ui.preview import PreviewWidget
    from bouncebeat.ui.properties import PropertiesPanel
    from bouncebeat.ui.render_dialog import RenderDialog
    from bouncebeat.ui.scene_tree import SceneTreePanel
    from bouncebeat.ui.settings_dialog import SettingsDialog
    from bouncebeat.ui.timeline import TimelineWidget
    from bouncebeat.ui.welcome import WelcomeDialog

    application = QApplication.instance() or QApplication([])
    project = BounceBeatProject()
    widgets = [
        PreviewWidget(),
        PropertiesPanel(),
        SceneTreePanel(),
        TimelineWidget(),
        MidiInspectorDialog(MidiAsset()),
        RenderDialog(project, FFmpegInfo()),
        SettingsDialog(AppSettings()),
        WelcomeDialog(FFmpegInfo(), ""),
    ]
    for widget in widgets:
        assert widget is not None
        widget.deleteLater()
    application.processEvents()
