from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _normalize_segment(segment: dict[str, Any], default_speaker: str = "UNKNOWN") -> dict[str, Any]:
    return {
        "speaker": segment.get("speaker") or default_speaker,
        "start": float(segment["start"]),
        "end": float(segment["end"]),
        "text": str(segment.get("text", "")).strip(),
    }


def normalize_transcript_payload(payload: dict[str, Any]) -> dict[str, Any]:
    segments = payload.get("segments") or []
    normalized = [_normalize_segment(segment) for segment in segments if isinstance(segment, dict)]
    return {
        "video_id": payload.get("video_id", ""),
        "language": payload.get("language", "en"),
        "model": payload.get("model", "unknown"),
        "diarization": payload.get("diarization", "unknown"),
        "segments": normalized,
    }

