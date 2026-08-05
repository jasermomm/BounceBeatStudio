from __future__ import annotations

import argparse
import sys

from bouncebeat.app import initialize
from bouncebeat.ui.main_window import MainWindow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch BounceBeat Studio")
    parser.add_argument("project", nargs="?", default="", help="Optional .bouncebeat project to open")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = initialize()
    window = MainWindow(args.project)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
