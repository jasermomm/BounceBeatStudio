from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "src"
if SOURCE.is_dir() and str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))


def _startup_log_path() -> Path:
    if sys.platform == "win32":
        root = Path(os.getenv("LOCALAPPDATA", tempfile.gettempdir())) / "BounceBeat Studio" / "logs"
    else:
        root = Path.home() / ".local" / "state" / "bouncebeat-studio" / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root / "startup-error.log"


def _report_startup_failure(message: str) -> None:
    path = _startup_log_path()
    path.write_text(
        f"BounceBeat Studio startup failure — {datetime.now().isoformat()}\n\n{message}\n\n{traceback.format_exc()}",
        encoding="utf-8",
    )
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"BounceBeat Studio could not start.\n\n{message}\n\nA detailed log was written to:\n{path}",
                "BounceBeat Studio",
                0x10,
            )
            return
        except Exception:
            pass
    print(f"BounceBeat Studio could not start: {message}\nLog: {path}", file=sys.stderr)


def main() -> int:
    try:
        from bouncebeat.main import main as application_main

        return application_main()
    except Exception as exc:
        _report_startup_failure(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
