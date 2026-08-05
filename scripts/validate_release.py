from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
if SOURCE.is_dir() and str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

import numpy as np
import soundfile as sf

from bouncebeat.audio.offline import render_note_events_to_wav
from bouncebeat.midi.parser import inspect_midi
from bouncebeat.models.enums import MidiMappingMode
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
from bouncebeat.presets.builtin import PRESET_NAMES, create_preset
from bouncebeat.recording.ffmpeg_export import FFmpegCommandBuilder
from bouncebeat.simulation.engine import SimulationEngine
from bouncebeat.utilities.ffmpeg import detect_ffmpeg
from bouncebeat.utilities.paths import resource_path


def _check_finite(snapshot, name: str) -> None:
    for state in snapshot.object_states.values():
        values = (*state.position, *state.velocity, state.rotation, state.radius)
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError(f"{name}: non-finite simulation state for {state.id}")


def validate_presets(require_native: bool) -> tuple[SimulationEngine, dict[str, object], bool]:
    render_engine: SimulationEngine | None = None
    native_physics_seen = False
    for name in PRESET_NAMES:
        project = create_preset(name)
        project.scene.physics.max_balls = min(project.scene.physics.max_balls, 300)
        engine = SimulationEngine(project, force_fallback=False)
        if engine.using_pymunk:
            native_physics_seen = True
        if require_native and not engine.using_pymunk:
            raise RuntimeError(
                f"{name}: Pymunk did not activate; native release validation cannot continue."
            )
        for _ in range(360):
            snapshot = engine.step()
        _check_finite(snapshot, name)
        if snapshot.active_ball_count > project.scene.physics.max_balls:
            raise RuntimeError(f"{name}: exceeded the project maximum-ball limit")
        if render_engine is None:
            render_engine = engine
    if render_engine is None:
        raise RuntimeError("No presets were available for validation")
    if require_native and not native_physics_seen:
        raise RuntimeError("No physical preset activated the native Pymunk backend")
    return render_engine, render_engine.models, native_physics_seen


def validate_qt_render(
    engine: SimulationEngine, models: dict[str, object], output: Path, require_native: bool
) -> str:
    try:
        from PySide6.QtWidgets import QApplication
        from bouncebeat.config.settings import AppSettings
        from bouncebeat.models.midi import MidiAsset
        from bouncebeat.rendering.qt_renderer import SceneRenderer
        from bouncebeat.ui.midi_dialog import MidiInspectorDialog
        from bouncebeat.ui.preview import PreviewWidget
        from bouncebeat.ui.properties import PropertiesPanel
        from bouncebeat.ui.render_dialog import RenderDialog
        from bouncebeat.ui.scene_tree import SceneTreePanel
        from bouncebeat.ui.settings_dialog import SettingsDialog
        from bouncebeat.ui.timeline import TimelineWidget
        from bouncebeat.ui.welcome import WelcomeDialog
        from bouncebeat.utilities.ffmpeg import FFmpegInfo
    except ImportError as exc:
        if require_native:
            raise RuntimeError(f"PySide6 UI is unavailable: {exc}") from exc
        return "Qt renderer unavailable; GUI smoke test skipped"
    application = QApplication.instance() or QApplication([])
    image = SceneRenderer().render(
        engine.project,
        engine.snapshot(),
        models,
        width=360,
        height=640,
        show_grid=False,
        show_safe_area=False,
        show_stats=True,
        actual_fps=60.0,
    )
    if image.isNull() or image.width() != 360 or image.height() != 640:
        raise RuntimeError("Qt scene renderer returned an invalid image")
    if not image.save(str(output)) or output.stat().st_size <= 0:
        raise RuntimeError("Qt scene renderer could not save its smoke-test image")
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
    project = create_preset("Classic Bounce")
    project.scene.objects = objects
    properties = PropertiesPanel()
    properties.set_context(project, None)
    for obj in objects:
        properties.set_context(project, obj)
        if properties.object is not obj or properties.object_layout.rowCount() <= 0:
            raise RuntimeError(f"Qt properties panel failed for {type(obj).__name__}")
    widgets = [
        properties,
        PreviewWidget(),
        SceneTreePanel(),
        TimelineWidget(),
        MidiInspectorDialog(MidiAsset()),
        RenderDialog(project, FFmpegInfo()),
        SettingsDialog(AppSettings()),
        WelcomeDialog(FFmpegInfo(), ""),
    ]
    for widget in widgets:
        widget.deleteLater()
    application.processEvents()
    return "Qt renderer and editor widgets: passed"


def validate_collision_audio(output: Path) -> Path:
    midi_path = resource_path("assets", "demo", "piano_bass_demo.mid")
    if not midi_path.is_file():
        raise RuntimeError(f"Packaged demo MIDI is missing: {midi_path}")
    project = create_preset("Classic Bounce")
    project.midi_asset = inspect_midi(midi_path)
    project.selected_track_ids = [track.id for track in project.midi_asset.playable_tracks()[:2]]
    project.midi_playback.mapping_mode = MidiMappingMode.LAYERED
    project.midi_playback.collision_cooldown_ms = 0
    for model in project.scene.objects:
        if isinstance(model, BallObject):
            model.midi_trigger = True
            model.collision_cooldown_ms = 0
    engine = SimulationEngine(project, force_fallback=False)
    for _ in range(1200):
        engine.step()
        if len(engine.note_events) >= 6:
            break
    if engine.snapshot().collision_count <= 0 or not engine.note_events:
        raise RuntimeError("Collision-to-MIDI validation produced no note events")
    duration = max(1.0, engine.time + 0.25)
    wav = render_note_events_to_wav(
        engine.note_events,
        duration,
        output,
        sample_rate=8000,
        waveform="sine",
        master_volume=0.75,
    )
    data, rate = sf.read(wav, always_2d=True)
    if rate != 8000 or len(data) != round(duration * rate) or data.shape[1] != 2:
        raise RuntimeError("Collision audio has the wrong duration, sample rate, or channel count")
    if float(np.max(np.abs(data))) <= 0.0 or not np.isfinite(data).all():
        raise RuntimeError("Collision audio is silent or contains invalid samples")
    return wav


def validate_ffmpeg(wav: Path, temp_dir: Path) -> str:
    info = detect_ffmpeg()
    if not info.available:
        return "FFmpeg not found; optional encode smoke test skipped"
    width, height, fps, frames = 160, 90, 30, 30
    video = temp_dir / "video.mkv"
    output = temp_dir / "release-smoke.mp4"
    command = FFmpegCommandBuilder.video_command(
        info.path, width, height, fps, "libx264", 24, "", False, video
    )
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    for index in range(frames):
        frame = np.zeros((height, width, 4), dtype=np.uint8)
        frame[..., 0] = (index * 7) % 255
        frame[..., 1] = np.arange(width, dtype=np.uint8)[None, :]
        frame[..., 2] = np.arange(height, dtype=np.uint8)[:, None]
        frame[..., 3] = 255
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    process.stdin = None
    code = process.wait(timeout=30)
    if code != 0:
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        raise RuntimeError(f"FFmpeg video smoke test failed: {stderr[-1000:]}")
    mux = FFmpegCommandBuilder.mux_command(
        info.path, video, wav, output, "aac", "128k", 1.0
    )
    result = subprocess.run(mux, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size <= 0:
        raise RuntimeError(f"FFmpeg mux smoke test failed: {result.stderr[-1000:]}")
    return f"FFmpeg encode/mux OK ({info.version})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a BounceBeat Studio release checkout")
    parser.add_argument(
        "--require-native",
        action="store_true",
        help="fail unless the real Pymunk backend is active (used by the Windows builder)",
    )
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    with tempfile.TemporaryDirectory(prefix="bouncebeat-release-check-") as temp_name:
        temp_dir = Path(temp_name)
        preset_engine, preset_models, native_physics_seen = validate_presets(args.require_native)
        qt_status = validate_qt_render(
            preset_engine, preset_models, temp_dir / "preview.png", args.require_native
        )
        collision_wav = validate_collision_audio(temp_dir / "collision-audio.wav")
        ffmpeg_status = validate_ffmpeg(collision_wav, temp_dir)

    print(f"Presets: {len(PRESET_NAMES)} passed")
    print(f"Physics backend: {'Pymunk' if native_physics_seen else 'deterministic fallback'}")
    print(qt_status)
    print("Collision -> MIDI -> stereo WAV: passed")
    print(ffmpeg_status)
    print("Release self-test: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
