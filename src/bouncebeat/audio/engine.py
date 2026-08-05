from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np
from PySide6.QtCore import QIODevice, QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

from bouncebeat.models.events import NoteEvent
from bouncebeat.models.scene import AudioSettings

from .fluidsynth_backend import FluidSynthBackend
from .synth import PolySynth

logger = logging.getLogger("bouncebeat.audio")


class _SynthIODevice(QIODevice):
    def __init__(self, synth: PolySynth, audio_format: QAudioFormat, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.synth = synth
        self.audio_format = audio_format

    def readData(self, maxlen: int) -> bytes:
        channels = max(1, self.audio_format.channelCount())
        sample_format = self.audio_format.sampleFormat()
        bytes_per_sample = 4 if sample_format == QAudioFormat.SampleFormat.Float else 2
        frames = max(1, maxlen // (channels * bytes_per_sample))
        samples = self.synth.render(frames, channels)
        if sample_format == QAudioFormat.SampleFormat.Float:
            return samples.astype("<f4", copy=False).tobytes()
        integer = (samples * 32767.0).astype("<i2")
        return integer.tobytes()

    def writeData(self, data: bytes) -> int:
        return 0

    def bytesAvailable(self) -> int:
        return 65536 + super().bytesAvailable()


class AudioEngine(QObject):
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self, settings: AudioSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.fallback = PolySynth(settings.sample_rate, polyphony=64)
        self.fallback.master_volume = settings.master_volume
        self.fluid = FluidSynthBackend(settings.sample_rate)
        self.sink: QAudioSink | None = None
        self.device: _SynthIODevice | None = None
        self.backend_name = "Fallback synth"
        self.started = False
        self._fluid_note_counts: dict[tuple[int, int], int] = defaultdict(int)

    def start(self) -> None:
        self.stop()
        if self.settings.backend in {"auto", "fluidsynth"} and self.settings.soundfont_path:
            if self.fluid.start(self.settings.soundfont_path):
                self.fluid.set_gain(self.settings.master_volume)
                self.backend_name = "FluidSynth"
                self.started = True
                self.status_changed.emit(f"FluidSynth: {self.settings.soundfont_path}")
                return
            if self.settings.backend == "fluidsynth":
                self.error.emit(self.fluid.error)
        try:
            output_device = QMediaDevices.defaultAudioOutput()
            if self.settings.audio_device and self.settings.audio_device != "default":
                output_device = next(
                    (device for device in QMediaDevices.audioOutputs() if device.description() == self.settings.audio_device),
                    output_device,
                )
            requested = QAudioFormat()
            requested.setSampleRate(self.settings.sample_rate)
            requested.setChannelCount(2)
            requested.setSampleFormat(QAudioFormat.SampleFormat.Float)
            audio_format = requested if output_device.isFormatSupported(requested) else output_device.preferredFormat()
            if audio_format.sampleFormat() not in {
                QAudioFormat.SampleFormat.Float,
                QAudioFormat.SampleFormat.Int16,
            }:
                audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self.fallback.sample_rate = audio_format.sampleRate()
            self.device = _SynthIODevice(self.fallback, audio_format, self)
            self.device.open(QIODevice.OpenModeFlag.ReadOnly)
            self.sink = QAudioSink(output_device, audio_format, self)
            requested_frames = max(
                self.settings.buffer_size,
                round(audio_format.sampleRate() * max(5, self.settings.latency_ms) / 1000),
            )
            self.sink.setBufferSize(max(2048, requested_frames * audio_format.bytesPerFrame()))
            self.sink.start(self.device)
            self.backend_name = "Built-in synth"
            self.started = True
            self.status_changed.emit("Built-in synthesizer ready")
        except Exception as exc:
            logger.exception("Audio output initialization failed")
            self.started = False
            self.error.emit(f"Audio output failed; preview will continue silently. {exc}")

    def play(self, events: list[NoteEvent]) -> None:
        if not self.started:
            return
        waveform = self.settings.fallback_waveform.value
        for event in events:


            velocity = round(event.velocity * event.volume)
            velocity = max(1, min(127, velocity))
            if self.fluid.available:
                key = (int(event.channel) % 16, int(event.pitch))
                self._fluid_note_counts[key] += 1
                self.fluid.note_on(event.pitch, velocity, event.channel, event.program)
                QTimer.singleShot(
                    max(1, round(event.duration * 1000)),
                    lambda p=event.pitch, c=event.channel: self._release_fluid_note(p, c),
                )
            else:
                self.fallback.note_on(event.pitch, velocity, event.duration, waveform, event.pan)

    def _release_fluid_note(self, pitch: int, channel: int) -> None:
        key = (int(channel) % 16, int(pitch))
        remaining = self._fluid_note_counts.get(key, 0) - 1
        if remaining > 0:
            self._fluid_note_counts[key] = remaining
            return
        self._fluid_note_counts.pop(key, None)
        self.fluid.note_off(pitch, channel)

    def panic(self) -> None:
        self._fluid_note_counts.clear()
        self.fallback.panic()
        self.fluid.panic()

    def set_master_volume(self, volume: float) -> None:
        self.settings.master_volume = max(0.0, min(1.0, volume))
        self.fallback.master_volume = self.settings.master_volume
        self.fluid.set_gain(self.settings.master_volume)

    def stop(self) -> None:
        self.panic()
        if self.sink:
            self.sink.stop()
            self.sink.deleteLater()
        if self.device:
            self.device.close()
            self.device.deleteLater()
        self.sink = None
        self.device = None
        self.fluid.stop()
        self.started = False
