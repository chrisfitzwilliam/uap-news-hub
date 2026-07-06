from __future__ import annotations

from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from ingest_sources import main as ingest_sources_main
from uap_news_hub.pipeline import PipelineResult, run_hourly, run_site_pipeline


def main(root: Path | None = None, *, ingest=ingest_sources_main) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    lock_path = root / "data" / "run.lock"

    def _run() -> PipelineResult:
        ingest_result = ingest(root)
        if ingest_result != 0:
            return PipelineResult(result="failed", details={"stage": "ingest", "exit_code": ingest_result})
        return run_site_pipeline(root, run_type="hourly")

    result = run_hourly(lock_path, run=_run)
    return 0 if result.result in {"success", "skipped_lock"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
