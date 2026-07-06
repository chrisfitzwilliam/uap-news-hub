from __future__ import annotations

from pathlib import Path


def cleanup_transcript_audio(download_dir: Path) -> list[Path]:
    removed: list[Path] = []
    for path in download_dir.rglob("audio.wav"):
        path.unlink(missing_ok=True)
        removed.append(path)
    return removed

