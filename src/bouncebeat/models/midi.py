from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class MidiNote:
    track_id: str
    track_index: int
    channel: int
    program: int
    pitch: int
    velocity: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(slots=True)
class MidiTrackInfo:
    id: str
    index: int
    name: str
    channel: int
    program: int
    instrument_name: str
    note_count: int
    lowest_note: int | None
    highest_note: int | None
    duration: float
    is_drum: bool
    is_empty: bool
    is_metadata_only: bool
    notes: list[MidiNote] = field(default_factory=list)
    volume: float = 1.0
    pan: float = 0.0
    muted: bool = False
    solo: bool = False


@dataclass(slots=True)
class MidiAsset:
    path: str = ""
    embedded_name: str = ""
    ticks_per_beat: int = 480
    duration: float = 0.0
    tracks: list[MidiTrackInfo] = field(default_factory=list)

    def playable_tracks(self) -> list[MidiTrackInfo]:
        return [track for track in self.tracks if track.note_count > 0 and not track.muted]

    def get_track(self, track_id: str) -> MidiTrackInfo | None:
        return next((track for track in self.tracks if track.id == track_id), None)
