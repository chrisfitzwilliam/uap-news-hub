import json
from pathlib import Path

from uap_news_hub.publish import publish_site
from uap_news_hub.settings import PipelineSettings
from uap_news_hub.state import StateStore


AUTONOMOUS = PipelineSettings("autonomous", True, False, "", 20, 80, 4, 2, 3, 25, "small", 14000)


def test_publish_site_commits_only_pipeline_owned_records(tmp_path):
    content_dir = tmp_path / "content"
    published_dir = content_dir / "published"
    published_dir.mkdir(parents=True)
    (tmp_path / "templates").mkdir()

    article = {
        "slug": "sample-briefing",
        "title": "Sample Briefing",
        "dek": "Summary",
        "content_type": "latest_briefing",
        "published_at": "2026-07-06T18:00:00Z",
        "confidence": "high",
        "source_urls": ["https://example.com/story"],
        "body_markdown": "# Heading\n\nBody text.",
        "review_result": "pass",
    }
    (published_dir / "sample-briefing.json").write_text(json.dumps(article), encoding="utf-8")

    calls = []
    result = publish_site(
        tmp_path,
        settings=AUTONOMOUS,
        status_provider=lambda root: "?? content/published/sample-briefing.json\n",
        git_runner=lambda root, *args: calls.append(args),
    )

    assert result.result == "success"
    assert calls[0] == ("add", "--", "content/published/", "content/queue/", "content/rejected/")
    assert calls[-1] == ("push", "origin", "main")

    with StateStore(tmp_path / "data" / "state.db") as state:
        state.initialize()
        run = state.latest_run("publish")
        assert run is not None
        assert run["result"] == "success"


def test_publish_site_fails_closed_on_invalid_json(tmp_path):
    published_dir = tmp_path / "content" / "published"
    published_dir.mkdir(parents=True)
    (tmp_path / "templates").mkdir()
    (published_dir / "broken.json").write_text("{not valid json", encoding="utf-8")

    result = publish_site(tmp_path)

    assert result.result == "failed"
    assert not (tmp_path / "_gh_pages").exists()


def test_publish_site_fails_closed_on_unexpected_dirty_source(tmp_path):
    content_dir = tmp_path / "content"
    published_dir = content_dir / "published"
    published_dir.mkdir(parents=True)
    (tmp_path / "templates").mkdir()
    (tmp_path / "README.md").write_text("manual edit", encoding="utf-8")

    article = {
        "slug": "sample-briefing",
        "title": "Sample Briefing",
        "dek": "Summary",
        "content_type": "latest_briefing",
        "published_at": "2026-07-06T18:00:00Z",
        "confidence": "high",
        "source_urls": ["https://example.com/story"],
        "body_markdown": "# Heading\n\nBody text.",
        "review_result": "pass",
    }
    (published_dir / "sample-briefing.json").write_text(json.dumps(article), encoding="utf-8")

    result = publish_site(tmp_path, settings=AUTONOMOUS, status_provider=lambda root: " M README.md\n")

    assert result.result == "failed"
    assert result.details["stage"] == "git_status"


def test_publish_site_respects_emergency_stop(tmp_path):
    (tmp_path / "content" / "published").mkdir(parents=True)
    result = publish_site(tmp_path, settings=PipelineSettings("autonomous", True, True, "", 20, 80, 4, 2, 3, 25, "small", 14000))
    assert result.result == "skipped"
    assert result.details["reason"] == "emergency_stop"
