from __future__ import annotations

from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from ingest_sources import main as ingest_sources_main
from download_youtube import main as download_youtube_main
from transcribe_diarize import main as transcribe_diarize_main
from uap_news_hub.pipeline import PipelineResult, run_daily, run_site_pipeline
from uap_news_hub.source_triage import run_source_triage_pipeline
from uap_news_hub.youtube_editorial import run_youtube_editorial_pipeline
from uap_news_hub.settings import load_settings
from uap_news_hub.observability import record_event
from uap_news_hub.publish import publish_site


def main(
    root: Path | None = None,
    *,
    ingest=ingest_sources_main,
    triage=None,
    download=download_youtube_main,
    transcribe=transcribe_diarize_main,
    editorial=run_youtube_editorial_pipeline,
    site_pipeline=run_site_pipeline,
    publisher=publish_site,
) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    settings = load_settings()
    triage = triage or run_source_triage_pipeline
    lock_path = root / "data" / "run.lock"

    def _run() -> PipelineResult:
        try:
            ingest_result = ingest(root, max_packets=settings.daily_packet_cap)
        except TypeError:
            ingest_result = ingest(root)
        if ingest_result != 0:
            return PipelineResult(result="failed", details={"stage": "ingest", "exit_code": ingest_result})
        triage_result = triage(root, budget_limit=settings.daily_agy_budget)
        if triage_result.agy_calls < 0:
            return PipelineResult(result="failed", details={"stage": "triage", "error": "invalid call count"})
        try:
            download_result = download(root, max_items=settings.daily_download_cap)
        except TypeError:
            download_result = download(root)
        if download_result != 0:
            return PipelineResult(result="failed", details={"stage": "download", "exit_code": download_result})
        try:
            transcribe_result = transcribe(root, max_items=settings.daily_transcription_cap)
        except TypeError:
            transcribe_result = transcribe(root)
        if transcribe_result != 0:
            return PipelineResult(result="failed", details={"stage": "transcribe", "exit_code": transcribe_result})
        editorial_budget = max(0, settings.daily_agy_budget - triage_result.agy_calls)
        try:
            editorial_result = editorial(root, budget_limit=editorial_budget, settings=settings)
        except TypeError:
            editorial_result = editorial(root, budget_limit=editorial_budget)
        result = site_pipeline(root, run_type="daily", agy_calls=triage_result.agy_calls + editorial_result.agy_calls)
        record_event(root, "daily_mode", mode=settings.mode, publishing_enabled=settings.publishing_enabled, emergency_stop=settings.emergency_stop)
        if result.result == "success" and settings.may_publish:
            publish_result = publisher(root, settings=settings)
            if publish_result.result == "failed":
                return publish_result
        return result

    result = run_daily(lock_path, run=_run)
    if result.result == "failed":
        record_event(root, "daily_failed", level="error", **result.details)
    return 0 if result.result in {"success", "skipped_lock"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
