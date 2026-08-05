from __future__ import annotations

import zipfile

from bouncebeat.midi.parser import inspect_midi
from bouncebeat.models.enums import ColorMode, MidiMappingMode
from bouncebeat.models.project import BounceBeatProject
from bouncebeat.presets.builtin import create_preset
from bouncebeat.projects.serializer import load_project, save_project


def test_project_serialization_round_trip(tmp_path, demo_midi_path):
    project = create_preset("Multi-Instrument Orchestra")
    project.name = "Acceptance Project"
    project.midi_asset = inspect_midi(demo_midi_path)
    project.selected_track_ids = ["track_1", "track_2"]
    project.scene.palette.colors = ["#FF4D6D", "#FFD166", "#06D6A0", "#118AB2", "#8338EC"]
    project.scene.palette.mode = ColorMode.CYCLE
    project.midi_playback.mapping_mode = MidiMappingMode.PER_BALL
    project.render.width = 1080
    project.render.height = 1920
    project.render.fps = 60
    project.recording.duration_seconds = 30
    project.scene.physics.continuous_collision_detection = True
    project.scene.physics.max_collision_substeps = 27
    project.scene.physics.collision_skin = 2.25

    path = save_project(project, tmp_path / "acceptance", embed_midi=True)
    loaded = load_project(path, tmp_path / "extracted")
    assert loaded.name == "Acceptance Project"
    assert loaded.selected_track_ids == ["track_1", "track_2"]
    assert loaded.scene.palette.colors == project.scene.palette.colors
    assert loaded.scene.palette.mode == ColorMode.CYCLE
    assert loaded.midi_playback.mapping_mode == MidiMappingMode.PER_BALL
    assert (loaded.render.width, loaded.render.height, loaded.render.fps) == (1080, 1920, 60)
    assert loaded.recording.duration_seconds == 30
    assert loaded.scene.physics.continuous_collision_detection is True
    assert loaded.scene.physics.max_collision_substeps == 27
    assert loaded.scene.physics.collision_skin == 2.25
    assert loaded.embedded_midi
    assert loaded.midi_asset.path.endswith("piano_bass.mid")


def test_project_is_zip_container_with_json(tmp_path):
    project = create_preset("Classic Bounce")
    path = save_project(project, tmp_path / "classic.bouncebeat")
    with zipfile.ZipFile(path) as archive:
        assert "project.json" in archive.namelist()


def test_to_dict_does_not_mutate_modified_timestamp():
    project = BounceBeatProject(name="Stable serialization")
    original = project.modified_at
    first = project.to_dict()
    second = project.to_dict()
    assert project.modified_at == original
    assert first == second


def test_saved_project_preserves_audio_settings(tmp_path):
    project = BounceBeatProject(name="Audio persistence")
    project.audio.master_volume = 0.37
    project.audio.sample_rate = 44100
    project.audio.buffer_size = 1024
    project.audio.audio_device = "Example Device"
    project.audio.latency_ms = 55
    path = save_project(project, tmp_path / "audio.bouncebeat")
    loaded = load_project(path)
    assert loaded.audio.master_volume == 0.37
    assert loaded.audio.sample_rate == 44100
    assert loaded.audio.buffer_size == 1024
    assert loaded.audio.audio_device == "Example Device"
    assert loaded.audio.latency_ms == 55
