from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from .build import build_site
from .locking import acquire_lock, release_lock
from .state import StateStore
from .utils import utc_now
from .validation import validate_published_content


@dataclass
class PipelineResult:
    result: str
    details: dict[str, Any]


def run_hourly(lock_path: Path, *, run: Callable[[], PipelineResult]) -> PipelineResult:
    lock = acquire_lock(lock_path, max_age_minutes=55)
    if not lock.acquired:
        return PipelineResult(result="skipped_lock", details={"reason": lock.reason})
    try:
        return run()
    finally:
        release_lock(lock_path)


def run_daily(lock_path: Path, *, run: Callable[[], PipelineResult]) -> PipelineResult:
    lock = acquire_lock(lock_path, max_age_minutes=6 * 60)
    if not lock.acquired:
        return PipelineResult(result="skipped_lock", details={"reason": lock.reason})
    try:
        return run()
    finally:
        release_lock(lock_path)


def run_site_pipeline(root: Path, *, run_type: str, agy_calls: int = 0) -> PipelineResult:
    root = Path(root)
    with StateStore(root / "data" / "state.db") as state:
        state.initialize()

        validation = validate_published_content(root / "content", state)
        started_at = utc_now()
        run_id = f"{run_type}-{started_at}"

        if not validation.passed:
            state.record_run(
                run_id=run_id,
                run_type=run_type,
                started_at=started_at,
                finished_at=started_at,
                result="failed",
                error_summary="; ".join(validation.errors[:5]),
            )
            return PipelineResult(result="failed", details={"stage": "validation", "errors": validation.errors})

        finished_at = utc_now()
        build_site(
            root / "content",
            root / "templates",
            root / "site",
            state,
            status_override={f"last_{run_type}_run": finished_at},
        )
        state.record_run(
            run_id=run_id,
            run_type=run_type,
            started_at=started_at,
            finished_at=finished_at,
            result="success",
            agy_calls=agy_calls,
        )
    return PipelineResult(result="success", details={"mode": run_type})
