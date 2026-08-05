# MIDI and audio

## Import and inspection

Import `.mid` or `.midi` files through the File menu, drag and drop, or recent-file list. The inspector reports track index, name, channel, program, General MIDI instrument, note count, range, duration, drum status, empty status, and metadata-only status.

Only playable tracks are selectable. Tracks remain separate; piano, bass, drums, and melody are never silently flattened.

## Mapping modes

- **Sequential:** advance the first selected or assigned track
- **Layered:** advance every selected track together
- **Round robin:** rotate between selected tracks
- **Random track:** deterministic seeded selection
- **Per ball:** each ball advances its own tracks
- **Per surface:** the contacted surface selects tracks
- **Timeline synchronized:** original MIDI timing plays while collisions drive visuals
- **Collision-controlled timeline:** each collision advances the next MIDI time group

The chord window groups notes starting within a configurable number of milliseconds.

## Playback transformations

Project controls include tempo multiplier, transpose, octave shift, velocity multiplier and clamp, default duration, sustain, loop, restart behavior, continue position, reverse, shuffle, quantization label, scale filter label, instrument override, channel override, and polyphony limit.

Track controls include volume, pan, mute, and solo. Object channel overrides take precedence where applicable.

## Collision-strength mappings

Collision strength can control note velocity, volume, duration, pitch, particles, glow, ball size pulse, and camera shake. The collision cooldown prevents sustained contacts from retriggering hundreds of notes.

## Live audio

The audio backend is selected automatically:

1. FluidSynth with a valid SoundFont when available
2. Built-in polyphonic synthesizer otherwise

Fallback waveforms are sine, square, triangle, and sawtooth. Audio settings include master volume, device label, sample rate, buffer size, and latency target. The Panic command stops active notes.

## Offline audio

The exporter records deterministic note events during simulation and renders a stereo WAV internally. When a SoundFont and FluidSynth executable are available, a temporary MIDI is rendered externally and then normalized to the exact requested sample rate, channel count, and sample count.

Overlapping equal-pitch notes are reference-counted so an earlier note-off cannot terminate a newer overlapping note. The final WAV duration is forced to match the video duration for long-render synchronization.

## SoundFont notes

SoundFonts are third-party assets and are not included. Confirm that the SoundFont license permits your intended use and distribution. A missing SoundFont never prevents the project from opening; the fallback synthesizer is used instead.
