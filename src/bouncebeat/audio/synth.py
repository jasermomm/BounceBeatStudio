from __future__ import annotations

import math
import threading
from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class Voice:
    pitch: int
    velocity: float
    duration_samples: int
    waveform: str
    pan: float
    phase: float = 0.0
    age_samples: int = 0
    released: bool = False
    release_age: int = 0


class PolySynth:
    def __init__(self, sample_rate: int = 48000, polyphony: int = 64) -> None:
        self.sample_rate = sample_rate
        self.polyphony = polyphony
        self.voices: list[Voice] = []
        self.lock = threading.RLock()
        self.master_volume = 0.8

    @staticmethod
    def frequency(pitch: int) -> float:
        return 440.0 * (2.0 ** ((pitch - 69) / 12.0))

    def note_on(self, pitch: int, velocity: int, duration: float, waveform: str = "sine", pan: float = 0.0) -> None:
        with self.lock:
            if len(self.voices) >= self.polyphony:
                self.voices.pop(0)
            self.voices.append(
                Voice(
                    pitch=max(0, min(127, pitch)),
                    velocity=max(0.0, min(1.0, velocity / 127.0)),
                    duration_samples=max(1, round(duration * self.sample_rate)),
                    waveform=waveform,
                    pan=max(-1.0, min(1.0, pan)),
                )
            )

    def note_off(self, pitch: int) -> None:
        with self.lock:
            for voice in self.voices:
                if voice.pitch == pitch:
                    voice.released = True

    def panic(self) -> None:
        with self.lock:
            self.voices.clear()

    def _wave(self, phase: np.ndarray, waveform: str) -> np.ndarray:
        if waveform == "square":
            return np.where(np.sin(phase) >= 0, 1.0, -1.0)
        if waveform == "triangle":
            return 2.0 / math.pi * np.arcsin(np.sin(phase))
        if waveform == "sawtooth":
            return 2.0 * ((phase / (2 * math.pi)) % 1.0) - 1.0
        return np.sin(phase)

    def render(self, frames: int, channels: int = 2) -> np.ndarray:
        frames = max(0, int(frames))
        output = np.zeros((frames, max(1, channels)), dtype=np.float32)
        if frames == 0:
            return output
        with self.lock:
            survivors: list[Voice] = []
            sample_indices = np.arange(frames, dtype=np.float64)
            for voice in self.voices:
                frequency = self.frequency(voice.pitch)
                phase_step = 2 * math.pi * frequency / self.sample_rate
                phases = voice.phase + sample_indices * phase_step
                signal = self._wave(phases, voice.waveform).astype(np.float32)
                absolute_age = voice.age_samples + np.arange(frames)
                attack = np.minimum(1.0, absolute_age / max(1, int(self.sample_rate * 0.008)))
                natural_release_start = max(1, voice.duration_samples - int(self.sample_rate * 0.06))
                natural_release = np.clip(
                    (voice.duration_samples - absolute_age) / max(1, int(self.sample_rate * 0.06)), 0.0, 1.0
                )
                envelope = np.where(absolute_age < natural_release_start, attack, np.minimum(attack, natural_release))
                if voice.released:
                    release = np.clip(1.0 - (voice.release_age + np.arange(frames)) / max(1, int(self.sample_rate * 0.05)), 0.0, 1.0)
                    envelope *= release
                    voice.release_age += frames
                signal *= envelope.astype(np.float32) * voice.velocity * self.master_volume * 0.22
                if channels == 1:
                    output[:, 0] += signal
                else:
                    left = math.sqrt((1.0 - voice.pan) * 0.5)
                    right = math.sqrt((1.0 + voice.pan) * 0.5)
                    output[:, 0] += signal * left
                    output[:, 1] += signal * right
                    for channel in range(2, channels):
                        output[:, channel] += signal * 0.5
                voice.phase = float((voice.phase + frames * phase_step) % (2 * math.pi))
                voice.age_samples += frames
                if voice.age_samples < voice.duration_samples and (not voice.released or voice.release_age < self.sample_rate * 0.05):
                    survivors.append(voice)
            self.voices = survivors
        np.clip(output, -1.0, 1.0, out=output)
        return output
