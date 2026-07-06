from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, urlparse

from .state import StateStore
from .transcripts import normalize_transcript_payload
from .urls import item_key_for_url, normalize_url
from .utils import ensure_parent, slugify, utc_now, write_json


ELIGIBLE_DOWNLOAD_STATUSES = {"new", "queued", "download_failed", "download_transcribe", "publish_candidate"}
ELIGIBLE_TRANSCRIPT_STATUSES = {"downloaded", "transcription_failed"}


@dataclass
class DownloadOutcome:
    packet_id: str
    video_id: str
    status: str
    attempts: int
    download_dir: Path
    error: str | None = None


@dataclass
class TranscriptOutcome:
    video_id: str
    status: str
    transcript_json: Path | None
    transcript_text: Path | None
    error: str | None = None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _video_id_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.netloc.endswith("youtu.be"):
        return parsed.path.strip("/")
    if parsed.netloc.endswith("youtube.com"):
        query = parse_qs(parsed.query)
        if "v" in query and query["v"]:
            return query["v"][0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.rsplit("/", 1)[-1]
    return ""


def _eligible_download_packet(packet: dict[str, Any]) -> bool:
    return packet.get("source_type") == "youtube" and packet.get("status", "new") in ELIGIBLE_DOWNLOAD_STATUSES


def _packet_files(packets_dir: Path) -> list[Path]:
    if not packets_dir.exists():
        return []
    return sorted(packets_dir.glob("*.json"))


def _download_root(root: Path) -> Path:
    return root / "data" / "downloads"


def _transcript_root(root: Path) -> Path:
    return root / "data" / "transcripts"


def _format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_transcript_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for segment in payload.get("segments", []):
        if not isinstance(segment, dict):
            continue
        speaker = str(segment.get("speaker") or "UNKNOWN")
        start = _format_timestamp(float(segment.get("start", 0.0)))
        end = _format_timestamp(float(segment.get("end", 0.0)))
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        lines.append(f"[{speaker} {start}-{end}] {text}")
    return "\n".join(lines)


def _normalize_audio(source_path: Path, target_path: Path, *, ffmpeg: str = "ffmpeg") -> None:
    ensure_parent(target_path)
    completed = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(target_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg normalization failed")


def default_youtube_downloader(packet: dict[str, Any], download_dir: Path) -> dict[str, Any]:
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:  # pragma: no cover - depends on local install
        raise RuntimeError("yt_dlp is required for YouTube downloads") from exc

    url = packet.get("source_url")
    if not url:
        raise ValueError("packet is missing source_url")

    download_dir.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bestaudio/best",
        "outtmpl": str(download_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "http_headers": {"User-Agent": "UAPNewsHub/1.0 (local pipeline)"},
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav", "preferredquality": "192"}],
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(str(url), download=True)

    raw_audio = Path(ydl.prepare_filename(info)).with_suffix(".wav")
    if not raw_audio.exists():
        wav_candidates = sorted(download_dir.glob("*.wav"), key=lambda candidate: candidate.stat().st_mtime)
        if not wav_candidates:
            raise RuntimeError("yt-dlp did not produce a wav file")
        raw_audio = wav_candidates[-1]

    audio_path = download_dir / "audio.wav"
    _normalize_audio(raw_audio, audio_path)
    if raw_audio != audio_path:
        raw_audio.unlink(missing_ok=True)
    (download_dir / "download.log").write_text(
        json.dumps(
            {
                "packet_id": packet.get("packet_id"),
                "source_url": packet.get("source_url"),
                "video_id": info.get("id"),
                "title": info.get("title"),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {"metadata": info, "audio_path": str(audio_path)}


def download_youtube_queue(
    root: Path,
    *,
    store: StateStore | None = None,
    downloader: Callable[[dict[str, Any], Path], dict[str, Any]] = default_youtube_downloader,
    delay_seconds: Callable[[], float] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_items: int | None = None,
) -> list[DownloadOutcome]:
    root = Path(root)
    packets_dir = root / "data" / "source-packets"
    download_root = _download_root(root)
    download_root.mkdir(parents=True, exist_ok=True)
    outcomes: list[DownloadOutcome] = []
    eligible_packets: list[Path] = []
    for packet_path in _packet_files(packets_dir):
        packet = _load_json(packet_path)
        if _eligible_download_packet(packet):
            eligible_packets.append(packet_path)

    def _process(store_obj: StateStore) -> list[DownloadOutcome]:
        processed = 0
        results: list[DownloadOutcome] = []
        for index, packet_path in enumerate(eligible_packets):
            if max_items is not None and processed >= max_items:
                break
            packet = _load_json(packet_path)
            video_url = str(packet.get("source_url", ""))
            video_id = _video_id_from_url(video_url) or slugify(str(packet.get("packet_id", packet_path.stem)))
            download_dir = download_root / video_id
            attempts = int(packet.get("download_attempts", 0))
            error_text: str | None = None
            status = "downloaded"
            try:
                result = downloader(packet, download_dir)
                metadata = dict(result.get("metadata") or {})
                metadata.update(
                    {
                        "packet_id": packet.get("packet_id"),
                        "source_url": video_url,
                        "video_id": metadata.get("id") or video_id,
                        "downloaded_at": utc_now(),
                        "status": "downloaded",
                        "audio_path": str(result.get("audio_path") or download_dir / "audio.wav"),
                    }
                )
                write_json(download_dir / "metadata.json", metadata)
                packet.update(
                    {
                        "status": "downloaded",
                        "download_attempts": attempts + 1,
                        "downloaded_at": metadata["downloaded_at"],
                        "download_dir": str(download_dir),
                        "video_id": metadata["video_id"],
                    }
                )
                store_obj.record_seen_item(
                    item_key_for_url(video_url),
                    "youtube",
                    "downloaded",
                    source_url=normalize_url(video_url),
                    title=str(packet.get("title", "")),
                    metadata={"packet_id": packet.get("packet_id"), "video_id": metadata["video_id"]},
                )
            except Exception as exc:
                attempts += 1
                error_text = str(exc)
                status = "download_abandoned" if attempts >= 3 else "download_failed"
                packet.update(
                    {
                        "status": status,
                        "download_attempts": attempts,
                        "last_download_error": error_text,
                    }
                )
                store_obj.record_seen_item(
                    item_key_for_url(video_url),
                    "youtube",
                    status,
                    source_url=normalize_url(video_url),
                    title=str(packet.get("title", "")),
                    metadata={"packet_id": packet.get("packet_id"), "error": error_text},
                )

            write_json(packet_path, packet)
            results.append(
                DownloadOutcome(
                    packet_id=str(packet.get("packet_id", packet_path.stem)),
                    video_id=video_id,
                    status=status,
                    attempts=attempts,
                    download_dir=download_dir,
                    error=error_text,
                )
            )
            processed += 1
            if max_items is not None and processed >= max_items:
                break
            if index < len(eligible_packets) - 1:
                delay = delay_seconds() if delay_seconds is not None else random.uniform(30.0, 120.0)
                sleep(delay)
        return results

    if store is not None:
        outcomes = _process(store)
        return outcomes

    with StateStore(root / "data" / "state.db") as store_obj:
        store_obj.initialize()
        outcomes = _process(store_obj)
    return outcomes


def default_transcriber(audio_path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # pragma: no cover - depends on local install
        raise RuntimeError("faster_whisper is required for transcription") from exc

    model_name = os.environ.get("UAP_WHISPER_MODEL", "small")
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    segments_iter, info = model.transcribe(str(audio_path), vad_filter=True)
    segments = []
    for segment in segments_iter:
        segments.append(
            {
                "speaker": "UNKNOWN",
                "start": float(segment.start),
                "end": float(segment.end),
                "text": str(segment.text).strip(),
            }
        )
    return {
        "video_id": metadata.get("video_id") or "",
        "language": getattr(info, "language", "en"),
        "model": model_name,
        "diarization": "unknown",
        "segments": segments,
    }


def transcribe_downloads(
    root: Path,
    *,
    store: StateStore | None = None,
    transcriber: Callable[[Path, dict[str, Any]], dict[str, Any]] = default_transcriber,
    transcript_root: Path | None = None,
    max_items: int | None = None,
) -> list[TranscriptOutcome]:
    root = Path(root)
    download_root = _download_root(root)
    transcript_root = Path(transcript_root) if transcript_root is not None else _transcript_root(root)
    transcript_root.mkdir(parents=True, exist_ok=True)
    download_dirs = sorted(path for path in download_root.iterdir() if path.is_dir()) if download_root.exists() else []
    outcomes: list[TranscriptOutcome] = []

    def _process(store_obj: StateStore) -> list[TranscriptOutcome]:
        processed = 0
        results: list[TranscriptOutcome] = []
        for download_dir in download_dirs:
            if max_items is not None and processed >= max_items:
                break
            metadata_path = download_dir / "metadata.json"
            audio_path = download_dir / "audio.wav"
            if not metadata_path.exists() or not audio_path.exists():
                continue
            metadata = _load_json(metadata_path)
            if metadata.get("status") not in ELIGIBLE_TRANSCRIPT_STATUSES and metadata.get("status") != "downloaded":
                continue
            video_id = str(metadata.get("video_id") or download_dir.name)
            transcript_json_path = transcript_root / f"{video_id}.json"
            transcript_text_path = transcript_root / f"{video_id}.txt"
            try:
                transcript_payload = transcriber(audio_path, metadata)
                transcript_payload = normalize_transcript_payload(transcript_payload)
                transcript_payload["video_id"] = video_id
                transcript_payload["source_url"] = metadata.get("source_url")
                transcript_payload["packet_id"] = metadata.get("packet_id")
                transcript_payload["download_dir"] = str(download_dir)
                transcript_payload["transcribed_at"] = utc_now()
                write_json(transcript_json_path, transcript_payload)
                transcript_text_path.write_text(_format_transcript_text(transcript_payload), encoding="utf-8")
                metadata.update(
                    {
                        "status": "transcribed",
                        "transcribed_at": transcript_payload["transcribed_at"],
                        "transcript_json": str(transcript_json_path),
                        "transcript_text": str(transcript_text_path),
                    }
                )
                store_obj.record_seen_item(
                    item_key_for_url(str(metadata.get("source_url", ""))),
                    "youtube",
                    "transcribed",
                    source_url=normalize_url(str(metadata.get("source_url", ""))),
                    title=str(metadata.get("title", "")),
                    metadata={"packet_id": metadata.get("packet_id"), "video_id": video_id},
                )
                status = "transcribed"
                error_text = None
            except Exception as exc:
                error_text = str(exc)
                metadata.update(
                    {
                        "status": "transcription_failed",
                        "transcription_error": error_text,
                    }
                )
                status = "transcription_failed"
                write_json(transcript_json_path, {"video_id": video_id, "segments": [], "diarization": "failed"})
                transcript_text_path.write_text("", encoding="utf-8")
                store_obj.record_seen_item(
                    item_key_for_url(str(metadata.get("source_url", ""))),
                    "youtube",
                    status,
                    source_url=normalize_url(str(metadata.get("source_url", ""))),
                    title=str(metadata.get("title", "")),
                    metadata={"packet_id": metadata.get("packet_id"), "error": error_text},
                )

            write_json(metadata_path, metadata)
            results.append(
                TranscriptOutcome(
                    video_id=video_id,
                    status=status,
                    transcript_json=transcript_json_path,
                    transcript_text=transcript_text_path,
                    error=error_text,
                )
            )
            processed += 1
        return results

    if store is not None:
        outcomes = _process(store)
        return outcomes

    with StateStore(root / "data" / "state.db") as store_obj:
        store_obj.initialize()
        outcomes = _process(store_obj)
    return outcomes
