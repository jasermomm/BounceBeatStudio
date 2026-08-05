from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bouncebeat.render",
        description="Render a BounceBeat project without opening the editor.",
    )
    parser.add_argument("project", help="Input .bouncebeat project")
    parser.add_argument("--output", required=True, help="Output video, WAV, or frame-sequence path")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--codec", default=None)
    parser.add_argument("--quality", type=int, default=None, help="CRF/quality value")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--transparent", action="store_true")
    parser.add_argument("--ffmpeg", default="", help="Custom FFmpeg executable")
    parser.add_argument("--realtime", action="store_true", help="Pace the render in real time")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    from bouncebeat.projects.serializer import load_project
    from bouncebeat.recording.ffmpeg_export import OfflineExporter, RenderProgress
    from bouncebeat.utilities.ffmpeg import detect_ffmpeg
    from bouncebeat.utilities.logging import configure_logging

    configure_logging()
    app = QGuiApplication.instance() or QGuiApplication(["bouncebeat-render"])
    project = load_project(args.project)
    if args.seed is not None:
        project.scene.physics.deterministic_seed = args.seed
    ffmpeg = detect_ffmpeg(args.ffmpeg)

    def progress(item: RenderProgress) -> None:
        print(
            f"\r{item.stage:10s} {item.percent:6.2f}% "
            f"frame {item.current_frame}/{item.total_frames} "
            f"sim {item.simulation_time:.2f}s speed {item.encoding_speed:.2f}x",
            end="",
            flush=True,
        )

    exporter = OfflineExporter(project, ffmpeg, progress_callback=progress)
    try:
        result = exporter.render(
            args.output,
            width=args.width,
            height=args.height,
            fps=args.fps,
            duration=args.duration,
            codec=args.codec,
            crf=args.quality,
            no_audio=args.no_audio,
            transparent=args.transparent,
            realtime=args.realtime,
        )
    except Exception as exc:
        print(f"\nRender failed: {exc}", file=sys.stderr)
        return 1
    print(f"\nSaved {result.output_path} ({result.frame_count} frames, {result.note_count} note events)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
