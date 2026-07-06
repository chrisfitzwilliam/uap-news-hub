import json
from pathlib import Path

from uap_news_hub.publish import publish_site
from uap_news_hub.state import StateStore


def test_publish_site_builds_and_deploys(tmp_path):
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

    result = publish_site(tmp_path)

    assert result.result == "success"
    assert (tmp_path / "_gh_pages" / "index.html").exists()

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
