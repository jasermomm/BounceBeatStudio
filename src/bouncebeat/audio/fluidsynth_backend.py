from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("bouncebeat.audio.fluidsynth")


class FluidSynthBackend:
    def __init__(self, sample_rate: int = 48000) -> None:
        self.sample_rate = sample_rate
        self.synth = None
        self.soundfont_id: int | None = None
        self.path = ""
        self.available = False
        self.error = ""

    def start(self, soundfont_path: str) -> bool:
        if not soundfont_path or not Path(soundfont_path).is_file():
            self.error = "No valid SoundFont was selected."
            return False
        try:
            import fluidsynth
        except ImportError as exc:
            self.error = f"pyFluidSynth is not installed: {exc}"
            return False
        try:
            self.synth = fluidsynth.Synth(samplerate=float(self.sample_rate))
            drivers = []
            if os.name == "nt":
                drivers = ["dsound", "wasapi", None]
            elif sys.platform == "darwin":
                drivers = ["coreaudio", None]
            else:
                drivers = ["pulseaudio", "pipewire", "alsa", None]
            started = False
            last_error: Exception | None = None
            for driver in drivers:
                try:
                    if driver:
                        self.synth.start(driver=driver)
                    else:
                        self.synth.start()
                    started = True
                    break
                except Exception as exc:
                    last_error = exc
            if not started:
                raise RuntimeError(f"Could not start a FluidSynth audio driver: {last_error}")
            self.soundfont_id = self.synth.sfload(soundfont_path)
            if self.soundfont_id < 0:
                raise RuntimeError("FluidSynth rejected the SoundFont file.")
            self.path = soundfont_path
            self.available = True
            self.error = ""
            return True
        except Exception as exc:
            self.error = str(exc)
            logger.exception("FluidSynth startup failed")
            self.stop()
            return False

    def note_on(self, pitch: int, velocity: int, channel: int = 0, program: int = 0) -> None:
        if not self.available or self.synth is None or self.soundfont_id is None:
            return
        channel = int(channel) % 16
        self.synth.program_select(channel, self.soundfont_id, 0, int(program) % 128)
        self.synth.noteon(channel, int(pitch), int(velocity))

    def note_off(self, pitch: int, channel: int = 0) -> None:
        if self.available and self.synth is not None:
            self.synth.noteoff(int(channel) % 16, int(pitch))

    def set_gain(self, gain: float) -> None:
        if self.available and self.synth is not None:
            try:
                self.synth.setting("synth.gain", float(gain))
            except Exception:
                pass

    def panic(self) -> None:
        if self.available and self.synth is not None:
            for channel in range(16):
                try:
                    self.synth.cc(channel, 123, 0)
                    self.synth.cc(channel, 120, 0)
                except Exception:
                    pass

    def stop(self) -> None:
        if self.synth is not None:
            try:
                self.panic()
                self.synth.delete()
            except Exception:
                pass
        self.synth = None
        self.available = False
        self.soundfont_id = None
