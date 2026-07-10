from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from .observability import record_event
from .pipeline import PipelineResult
from .settings import PipelineSettings, load_settings
from .state import StateStore
from .utils import utc_now
from .validation import validate_published_content


ALLOWED_PIPELINE_PATH_PREFIXES = (
    "content/published/",
    "content/queue/",
    "content/rejected/",
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _git_status_porcelain(root: Path) -> str:
    return _git(root, "status", "--porcelain=v1").stdout


def _status_path(line: str) -> str:
    path = line[3:].strip() if len(line) > 3 else line.strip()
    # A rename reports "old -> new"; both ends must be owned.
    return path.replace("\\", "/")


def unexpected_pipeline_changes(status_text: str) -> list[str]:
    unexpected: list[str] = []
    for raw in status_text.splitlines():
        path = _status_path(raw)
        candidates = [part.strip() for part in path.split(" -> ")]
        if not candidates or any(not candidate.startswith(ALLOWED_PIPELINE_PATH_PREFIXES) for candidate in candidates):
            unexpected.append(raw)
    return unexpected


def publish_site(
    root: Path,
    *,
    settings: PipelineSettings | None = None,
    status_provider: Callable[[Path], str] | None = None,
    git_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> PipelineResult:
    """Commit only pipeline-owned editorial records; Pages builds in GitHub Actions."""
    root = Path(root)
    settings = settings or load_settings()
    started_at = utc_now()
    run_id = f"publish-{started_at}"
    with StateStore(root / "data" / "state.db") as state:
        state.initialize()
        validation = validate_published_content(root / "content", state)
        if not validation.passed:
            state.record_run(run_id=run_id, run_type="publish", started_at=started_at, finished_at=utc_now(), result="failed", error_summary="; ".join(validation.errors[:5]))
            record_event(root, "publish_failed", level="error", stage="validation", errors=validation.errors[:5])
            return PipelineResult("failed", {"stage": "validation", "errors": validation.errors})
        if not settings.may_publish:
            reason = "emergency_stop" if settings.emergency_stop else "publish_not_enabled" if not settings.publishing_enabled else settings.mode
            state.record_run(run_id=run_id, run_type="publish", started_at=started_at, finished_at=utc_now(), result="skipped", error_summary=reason)
            record_event(root, "publish_skipped", level="warning", reason=reason)
            return PipelineResult("skipped", {"reason": reason})
        try:
            status = (status_provider or _git_status_porcelain)(root)
            unexpected = unexpected_pipeline_changes(status)
            if unexpected:
                state.record_run(run_id=run_id, run_type="publish", started_at=started_at, finished_at=utc_now(), result="failed", error_summary="unexpected dirty source changes")
                record_event(root, "publish_failed", level="error", stage="git_status", unexpected=unexpected)
                return PipelineResult("failed", {"stage": "git_status", "unexpected": unexpected})
            if not status.strip():
                state.record_run(run_id=run_id, run_type="publish", started_at=started_at, finished_at=utc_now(), result="skipped", error_summary="no pipeline-owned changes")
                return PipelineResult("skipped", {"reason": "no_changes"})
            runner = git_runner or _git
            runner(root, "add", "--", *ALLOWED_PIPELINE_PATH_PREFIXES)
            runner(root, "commit", "-m", f"Publish validated UAP editorial update ({started_at})")
            runner(root, "push", "origin", "main")
        except Exception as exc:
            state.record_run(run_id=run_id, run_type="publish", started_at=started_at, finished_at=utc_now(), result="failed", error_summary=str(exc))
            record_event(root, "publish_failed", level="error", stage="git", error=str(exc))
            return PipelineResult("failed", {"stage": "git", "error": str(exc)})
        state.record_run(run_id=run_id, run_type="publish", started_at=started_at, finished_at=utc_now(), result="success")
        record_event(root, "publish_success", commit_message=f"Publish validated UAP editorial update ({started_at})")
    return PipelineResult("success", {"mode": "source_commit", "branch": "main"})
