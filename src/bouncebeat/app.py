from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from bouncebeat.utilities.logging import configure_logging
from bouncebeat.utilities.paths import resource_path

logger = logging.getLogger("bouncebeat.app")


def create_application(argv: list[str] | None = None) -> QApplication:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("BounceBeat Studio")
    app.setApplicationDisplayName("BounceBeat Studio")
    app.setOrganizationName("BounceBeat")
    app.setOrganizationDomain("bouncebeat.local")
    app.setStyle("Fusion")
    icon_path = resource_path("assets", "icons", "app.svg")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    theme_path = resource_path("assets", "themes", "dark.qss")
    if theme_path.is_file():
        app.setStyleSheet(theme_path.read_text(encoding="utf-8"))
    return app


def install_exception_hook() -> None:
    def handle(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical("Unhandled exception\n%s", details)
        try:
            QMessageBox.critical(
                None,
                "BounceBeat Studio encountered an error",
                f"{exc_value}\n\nThe complete technical details were written to the application log.",
            )
        except Exception:
            pass
    sys.excepthook = handle


def initialize() -> QApplication:
    configure_logging()
    install_exception_hook()
    return create_application()
