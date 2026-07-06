from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .utils import ensure_parent, utc_now


@dataclass
class LockResult:
    acquired: bool
    stale_recovered: bool = False
    reason: str | None = None


def _parse_iso_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def acquire_lock(lock_path: Path, *, max_age_minutes: int) -> LockResult:
    ensure_parent(lock_path)
    if lock_path.exists():
        payload = lock_path.read_text(encoding="utf-8").strip().splitlines()
        pid = None
        started_at = None
        for line in payload:
            if line.startswith("pid="):
                pid = int(line.split("=", 1)[1])
            if line.startswith("started_at="):
                started_at = line.split("=", 1)[1]
        stale = True
        if pid is not None:
            stale = not _process_running(pid)
        if started_at:
            age = datetime.now(timezone.utc) - _parse_iso_timestamp(started_at)
            stale = stale or age.total_seconds() > max_age_minutes * 60
        if not stale:
            return LockResult(acquired=False, reason="locked")
        lock_path.unlink(missing_ok=True)
        recovered = True
    else:
        recovered = False
    lock_path.write_text(f"pid={os.getpid()}\nstarted_at={utc_now()}\n", encoding="utf-8")
    return LockResult(acquired=True, stale_recovered=recovered)


def release_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


def _process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

