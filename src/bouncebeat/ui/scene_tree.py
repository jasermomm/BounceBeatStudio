from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bouncebeat.models.enums import ObjectKind
from bouncebeat.models.scene import Scene


class _ObjectTree(QTreeWidget):
    reordered = Signal(object)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        ids = []
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            ids.append(item.data(0, Qt.ItemDataRole.UserRole))
        self.reordered.emit(ids)


class SceneTreePanel(QWidget):
    selected = Signal(str)
    add_requested = Signal(str)
    duplicate_requested = Signal(str)
    delete_requested = Signal(str)
    visibility_changed = Signal(str, bool)
    lock_changed = Signal(str, bool)
    reordered = Signal(object)
    group_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.tree = _ObjectTree()
        self.tree.setHeaderLabels(["Name", "Type", "Visible", "Locked"])
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        self.tree.itemChanged.connect(self._item_changed)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.reordered.connect(self.reordered)
        layout.addWidget(self.tree)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("+")
        self.add_button.setToolTip("Add an object")
        self.duplicate_button = QPushButton("Duplicate")
        self.delete_button = QPushButton("Delete")
        self.group_button = QPushButton("Group")
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.duplicate_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.group_button)
        layout.addLayout(buttons)
        self.add_menu = QMenu(self)
        for kind, label in [
            (ObjectKind.BALL, "Ball"), (ObjectKind.WALL, "Wall"), (ObjectKind.RING, "Ring"),
            (ObjectKind.BUMPER, "Bumper"), (ObjectKind.POLYGON, "Rotating obstacle"),
            (ObjectKind.PORTAL, "Portal"), (ObjectKind.EMITTER, "Emitter"),
            (ObjectKind.TEXT, "Text overlay"), (ObjectKind.PARTICLE_SYSTEM, "Particle system"),
        ]:
            action = self.add_menu.addAction(label)
            action.triggered.connect(lambda checked=False, value=kind.value: self.add_requested.emit(value))
        self.add_button.clicked.connect(lambda: self.add_menu.exec(self.add_button.mapToGlobal(self.add_button.rect().bottomLeft())))
        self.duplicate_button.clicked.connect(self._duplicate)
        self.delete_button.clicked.connect(self._delete)
        self.group_button.clicked.connect(self._group)

    def set_scene(self, scene: Scene, selected_id: str | None = None) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        for obj in scene.objects:
            item = QTreeWidgetItem([obj.name, obj.kind.value.replace("_", " ").title(), "", ""])
            item.setData(0, Qt.ItemDataRole.UserRole, obj.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            item.setCheckState(2, Qt.CheckState.Checked if obj.visible else Qt.CheckState.Unchecked)
            item.setCheckState(3, Qt.CheckState.Checked if obj.locked else Qt.CheckState.Unchecked)
            if obj.group:
                item.setToolTip(0, f"Group: {obj.group}")
            self.tree.addTopLevelItem(item)
            if obj.id == selected_id:
                item.setSelected(True)
        self.tree.blockSignals(False)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)

    def selected_ids(self) -> list[str]:
        return [item.data(0, Qt.ItemDataRole.UserRole) for item in self.tree.selectedItems()]

    def _selection_changed(self) -> None:
        ids = self.selected_ids()
        if ids:
            self.selected.emit(ids[0])

    def _item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        object_id = item.data(0, Qt.ItemDataRole.UserRole)
        if column == 2:
            self.visibility_changed.emit(object_id, item.checkState(2) == Qt.CheckState.Checked)
        elif column == 3:
            self.lock_changed.emit(object_id, item.checkState(3) == Qt.CheckState.Checked)

    def _duplicate(self) -> None:
        ids = self.selected_ids()
        if ids:
            self.duplicate_requested.emit(ids[0])

    def _delete(self) -> None:
        ids = self.selected_ids()
        if ids:
            self.delete_requested.emit(ids[0])

    def _group(self) -> None:
        ids = self.selected_ids()
        if ids:
            self.group_requested.emit(ids)

    def _context_menu(self, point) -> None:
        menu = QMenu(self)
        duplicate = menu.addAction("Duplicate")
        delete = menu.addAction("Delete")
        group = menu.addAction("Group selected")
        chosen = menu.exec(self.tree.viewport().mapToGlobal(point))
        if chosen == duplicate:
            self._duplicate()
        elif chosen == delete:
            self._delete()
        elif chosen == group:
            self._group()
