from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bouncebeat import __version__

from .midi import MidiAsset, MidiNote, MidiTrackInfo
from .scene import (
    AudioSettings,
    CameraSettings,
    MidiPlaybackSettings,
    RecordingSettings,
    RenderSettings,
    Scene,
    TimelineSettings,
    dataclass_from_dict,
    dataclass_to_dict,
    scene_from_dict,
    scene_to_dict,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class BounceBeatProject:
    format_version: int = 1
    application_version: str = __version__
    name: str = "Untitled Project"
    created_at: str = field(default_factory=utc_now)
    modified_at: str = field(default_factory=utc_now)
    scene: Scene = field(default_factory=Scene)
    midi_asset: MidiAsset = field(default_factory=MidiAsset)
    selected_track_ids: list[str] = field(default_factory=list)
    midi_playback: MidiPlaybackSettings = field(default_factory=MidiPlaybackSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    render: RenderSettings = field(default_factory=RenderSettings)
    recording: RecordingSettings = field(default_factory=RecordingSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
    timeline: TimelineSettings = field(default_factory=TimelineSettings)
    project_path: str = ""
    embedded_midi: bool = False
    preset_name: str = "Blank"
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.modified_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "application_version": self.application_version,
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "scene": scene_to_dict(self.scene),
            "midi_asset": midi_asset_to_dict(self.midi_asset),
            "selected_track_ids": list(self.selected_track_ids),
            "midi_playback": dataclass_to_dict(self.midi_playback),
            "audio": dataclass_to_dict(self.audio),
            "render": dataclass_to_dict(self.render),
            "recording": dataclass_to_dict(self.recording),
            "camera": dataclass_to_dict(self.camera),
            "timeline": dataclass_to_dict(self.timeline),
            "embedded_midi": self.embedded_midi,
            "preset_name": self.preset_name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BounceBeatProject":
        project = cls(
            format_version=int(data.get("format_version", 1)),
            application_version=str(data.get("application_version", __version__)),
            name=str(data.get("name", "Untitled Project")),
            created_at=str(data.get("created_at", utc_now())),
            modified_at=str(data.get("modified_at", utc_now())),
            scene=scene_from_dict(data.get("scene", {})),
            midi_asset=midi_asset_from_dict(data.get("midi_asset", {})),
            selected_track_ids=list(data.get("selected_track_ids", [])),
            midi_playback=dataclass_from_dict(MidiPlaybackSettings, data.get("midi_playback", {})),
            audio=dataclass_from_dict(AudioSettings, data.get("audio", {})),
            render=dataclass_from_dict(RenderSettings, data.get("render", {})),
            recording=dataclass_from_dict(RecordingSettings, data.get("recording", {})),
            camera=dataclass_from_dict(CameraSettings, data.get("camera", {})),
            timeline=dataclass_from_dict(TimelineSettings, data.get("timeline", {})),
            embedded_midi=bool(data.get("embedded_midi", False)),
            preset_name=str(data.get("preset_name", "Blank")),
            metadata=dict(data.get("metadata", {})),
        )
        return project


def midi_asset_to_dict(asset: MidiAsset) -> dict[str, Any]:
    return {
        "path": asset.path,
        "embedded_name": asset.embedded_name,
        "ticks_per_beat": asset.ticks_per_beat,
        "duration": asset.duration,
        "tracks": [
            {
                "id": track.id,
                "index": track.index,
                "name": track.name,
                "channel": track.channel,
                "program": track.program,
                "instrument_name": track.instrument_name,
                "note_count": track.note_count,
                "lowest_note": track.lowest_note,
                "highest_note": track.highest_note,
                "duration": track.duration,
                "is_drum": track.is_drum,
                "is_empty": track.is_empty,
                "is_metadata_only": track.is_metadata_only,
                "volume": track.volume,
                "pan": track.pan,
                "muted": track.muted,
                "solo": track.solo,
                "notes": [dataclass_to_dict(note) for note in track.notes],
            }
            for track in asset.tracks
        ],
    }


def midi_asset_from_dict(data: dict[str, Any]) -> MidiAsset:
    tracks: list[MidiTrackInfo] = []
    for track_data in data.get("tracks", []):
        notes = [MidiNote(**note_data) for note_data in track_data.get("notes", [])]
        track_kwargs = {key: value for key, value in track_data.items() if key != "notes"}
        tracks.append(MidiTrackInfo(notes=notes, **track_kwargs))
    return MidiAsset(
        path=str(data.get("path", "")),
        embedded_name=str(data.get("embedded_name", "")),
        ticks_per_beat=int(data.get("ticks_per_beat", 480)),
        duration=float(data.get("duration", 0.0)),
        tracks=tracks,
    )
