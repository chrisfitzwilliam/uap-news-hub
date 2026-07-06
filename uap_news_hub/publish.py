from __future__ import annotations

import shutil
from pathlib import Path

from .build import build_site
from .pipeline import PipelineResult
from .state import StateStore
from .utils import utc_now
from .validation import validate_published_content


def deploy_site_to_branch(site_dir: Path, branch_dir: Path) -> None:
    if branch_dir.exists():
        shutil.rmtree(branch_dir)
    shutil.copytree(site_dir, branch_dir)


def publish_site(root: Path, *, branch_dir_name: str = "_gh_pages") -> PipelineResult:
    root = Path(root)
    with StateStore(root / "data" / "state.db") as state:
        state.initialize()

        started_at = utc_now()
        finished_at = started_at
        run_id = f"publish-{started_at}"
        validation = validate_published_content(root / "content", state)
        if not validation.passed:
            state.record_run(
                run_id=run_id,
                run_type="publish",
                started_at=started_at,
                finished_at=finished_at,
                result="failed",
                error_summary="; ".join(validation.errors[:5]),
            )
            return PipelineResult(result="failed", details={"stage": "validation", "errors": validation.errors})

        try:
            build_site(
                root / "content",
                root / "templates",
                root / "site",
                state,
                status_override={"last_publish": finished_at},
            )
            deploy_site_to_branch(root / "site", root / branch_dir_name)
        except Exception as exc:
            state.record_run(
                run_id=run_id,
                run_type="publish",
                started_at=started_at,
                finished_at=utc_now(),
                result="failed",
                error_summary=str(exc),
            )
            return PipelineResult(result="failed", details={"stage": "deploy", "error": str(exc)})

        state.record_run(
            run_id=run_id,
            run_type="publish",
            started_at=started_at,
            finished_at=finished_at,
            result="success",
        )
    return PipelineResult(result="success", details={"mode": "publish", "branch_dir": str(root / branch_dir_name)})
