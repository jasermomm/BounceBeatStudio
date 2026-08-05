from __future__ import annotations

import os

import pytest

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


def test_properties_panel_builds_for_every_scene_object_type():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from bouncebeat.ui.properties import PropertiesPanel

    application = QApplication.instance() or QApplication([])
    objects = [
        BallObject(),
        WallObject(),
        RingObject(),
        BumperObject(),
        PolygonObject(),
        PortalObject(),
        EmitterObject(),
        TextOverlayObject(),
        ParticleSystemObject(),
    ]
    project = BounceBeatProject()
    project.scene.objects = objects
    panel = PropertiesPanel()

    panel.set_context(project, None)
    for obj in objects:
        panel.set_context(project, obj)
        assert panel.object is obj
        assert panel.object_layout.rowCount() > 0

    panel.deleteLater()
    application.processEvents()
