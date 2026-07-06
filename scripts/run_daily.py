from __future__ import annotations

from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from ingest_sources import main as ingest_sources_main
from download_youtube import main as download_youtube_main
from triage_sources import main as triage_sources_main
from transcribe_diarize import main as transcribe_diarize_main
from uap_news_hub.pipeline import PipelineResult, run_daily, run_site_pipeline
from uap_news_hub.youtube_editorial import run_youtube_editorial_pipeline


def main(
    root: Path | None = None,
    *,
    ingest=ingest_sources_main,
    triage=triage_sources_main,
    download=download_youtube_main,
    transcribe=transcribe_diarize_main,
    editorial=run_youtube_editorial_pipeline,
    site_pipeline=run_site_pipeline,
) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    lock_path = root / "data" / "run.lock"

    def _run() -> PipelineResult:
        ingest_result = ingest(root)
        if ingest_result != 0:
            return PipelineResult(result="failed", details={"stage": "ingest", "exit_code": ingest_result})
        triage_result = triage(root, budget_limit=25)
        if triage_result.agy_calls < 0:
            return PipelineResult(result="failed", details={"stage": "triage", "error": "invalid call count"})
        download_result = download(root)
        if download_result != 0:
            return PipelineResult(result="failed", details={"stage": "download", "exit_code": download_result})
        transcribe_result = transcribe(root)
        if transcribe_result != 0:
            return PipelineResult(result="failed", details={"stage": "transcribe", "exit_code": transcribe_result})
        editorial_budget = max(0, 25 - triage_result.agy_calls)
        editorial_result = editorial(root, budget_limit=editorial_budget)
        return site_pipeline(root, run_type="daily", agy_calls=triage_result.agy_calls + editorial_result.agy_calls)

    result = run_daily(lock_path, run=_run)
    return 0 if result.result in {"success", "skipped_lock"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
