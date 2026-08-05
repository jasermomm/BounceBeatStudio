from __future__ import annotations

import numpy as np
import soundfile as sf

from bouncebeat.audio.offline import render_fallback_audio, render_note_events_to_wav
from bouncebeat.models.events import NoteEvent


def note() -> NoteEvent:
    return NoteEvent(
        time=0.1, pitch=69, velocity=100, duration=0.25, track_id="track_1",
        channel=0, program=0, pan=0.0, volume=1.0, source_object_id="ball",
    )


def test_fallback_audio_shape_and_signal():
    audio = render_fallback_audio([note()], 1.0, sample_rate=8000)
    assert audio.shape == (8000, 2)
    assert audio.dtype == np.float32
    assert float(np.max(np.abs(audio))) > 0


def test_wav_export_has_requested_duration(tmp_path):
    path = render_note_events_to_wav([note()], 1.0, tmp_path / "test.wav", sample_rate=8000)
    data, sample_rate = sf.read(path)
    assert sample_rate == 8000
    assert len(data) == 8000
