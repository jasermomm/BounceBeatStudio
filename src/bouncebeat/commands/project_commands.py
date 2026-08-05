from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QUndoCommand


class ProjectSnapshotCommand(QUndoCommand):
    def __init__(
        self,
        text: str,
        before: dict,
        after: dict,
        apply_callback: Callable[[dict], None],
        already_applied: bool = True,
    ) -> None:
        super().__init__(text)
        self.before = before
        self.after = after
        self.apply_callback = apply_callback
        self._skip_first_redo = already_applied

    def undo(self) -> None:
        self.apply_callback(self.before)

    def redo(self) -> None:
        if self._skip_first_redo:
            self._skip_first_redo = False
            return
        self.apply_callback(self.after)
