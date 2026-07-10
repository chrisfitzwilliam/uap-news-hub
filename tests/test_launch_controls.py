import json
from pathlib import Path

import pytest

from uap_news_hub.agy import AgyRunResult
from uap_news_hub.publish import unexpected_pipeline_changes
from uap_news_hub.settings import load_settings
from uap_news_hub.youtube_editorial import chunk_transcript, run_youtube_editorial_pipeline


def test_environment_parses_publish_controls_and_limits():
    settings = load_settings({
        "UAPNEWSHUB_PIPELINE_MODE": "autonomous",
        "UAPNEWSHUB_ENABLE_PUBLISH": "true",
        "UAPNEWSHUB_DAILY_DOWNLOAD_CAP": "3",
        "UAPNEWSHUB_DAILY_TRANSCRIPTION_CAP": "2",
        "UAPNEWSHUB_SITE_URL": "https://news.example",
    })
    assert settings.may_publish
    assert settings.daily_download_cap == 3
    assert settings.site_url == "https://news.example"
    with pytest.raises(ValueError):
        load_settings({"UAPNEWSHUB_PIPELINE_MODE": "unsafe"})


def test_chunk_transcript_preserves_segments_and_bounds_chunks():
    transcript = {"video_id": "video", "segments": [{"start": i, "end": i + 1, "text": "x" * 600} for i in range(5)]}
    chunks = chunk_transcript(transcript, max_chars=1400)
    assert len(chunks) == 3
    assert sum(len(chunk["segments"]) for chunk in chunks) == 5


def test_dry_run_never_writes_public_or_queue_content(tmp_path):
    video_id = "video"
    source_url = "https://www.youtube.com/watch?v=video"
    download_dir = tmp_path / "data" / "downloads" / video_id
    transcript_dir = tmp_path / "data" / "transcripts"
    download_dir.mkdir(parents=True)
    transcript_dir.mkdir(parents=True)
    (download_dir / "metadata.json").write_text(json.dumps({"packet_id": "p", "video_id": video_id, "source_url": source_url, "title": "Video"}), encoding="utf-8")
    (transcript_dir / "video.json").write_text(json.dumps({"video_id": video_id, "source_url": source_url, "segments": [{"start": 0, "end": 1, "text": "A source-grounded statement."}]}), encoding="utf-8")
    payloads = [
        {"packet_id": "p", "video_id": video_id, "summary": "Summary", "segments": [], "speakers": [], "key_claims": [], "article_recommendation": "draft_youtube_intel", "publication_risk": "low", "open_questions": []},
        {"slug": "video", "title": "Video", "dek": "Summary", "content_type": "youtube_intel", "confidence": "low", "claim_labels": ["analysis"], "sources": [{"title": "Video", "url": source_url, "type": "primary"}], "article_markdown": "Body.", "related_claims": [], "should_publish": True},
        {"review_result": "pass", "blocking_issues": [], "non_blocking_warnings": [], "required_edits": [], "confidence_after_review": "low"},
    ]
    def runner(prompt, *, save_dir=None):
        payload = payloads.pop(0)
        return AgyRunResult(json.dumps(payload), payload, 1, save_dir)
    settings = load_settings({"UAPNEWSHUB_PIPELINE_MODE": "dry-run"})
    outcome = run_youtube_editorial_pipeline(tmp_path, runner=runner, settings=settings, max_items=1)
    assert len(outcome.outcomes) == 1
    assert not (tmp_path / "content" / "published").exists()
    assert not (tmp_path / "content" / "queue").exists()


def test_unexpected_git_changes_fail_closed():
    assert unexpected_pipeline_changes("?? content/published/a.json\n") == []
    assert unexpected_pipeline_changes(" M README.md\n") == [" M README.md"]
    assert unexpected_pipeline_changes("?? data/state.db\n") == ["?? data/state.db"]


def test_pages_workflow_uses_source_build_inputs():
    workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pages.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "python-version: '3.12'" in text
    assert "python scripts/validate_outputs.py" in text
    assert "actions/upload-pages-artifact@v3" in text
    assert "actions/deploy-pages@v4" in text


def test_scheduler_script_has_idempotent_no_overlap_controls():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "install_task_scheduler.ps1").read_text(encoding="utf-8")
    assert "Register-ScheduledTask" in script
    assert "-MultipleInstances IgnoreNew" in script
    assert "uninstall" in script
