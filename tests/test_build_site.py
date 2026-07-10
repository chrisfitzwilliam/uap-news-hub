import hashlib
import json
from pathlib import Path

from uap_news_hub.build import build_site
from uap_news_hub.state import StateStore


def _digest_tree(path: Path) -> dict[str, str]:
    result = {}
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        result[str(file_path.relative_to(path))] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return result


def test_build_site_is_deterministic(tmp_path):
    content_dir = tmp_path / "content"
    templates_dir = tmp_path / "templates"
    site_dir = tmp_path / "site"
    for directory in (content_dir, templates_dir):
        directory.mkdir()

    with StateStore(tmp_path / "state.db") as state:
        state.initialize()
        state.record_published_index(
            slug="sample-briefing",
            title="Sample Briefing",
            content_type="latest_briefing",
            source_urls=["https://example.com/story"],
            published_at="2026-07-06T18:00:00Z",
        )

        article = {
            "slug": "sample-briefing",
            "title": "Sample Briefing",
            "dek": "Summary",
            "content_type": "latest_briefing",
            "published_at": "2026-07-06T18:00:00Z",
            "confidence": "high",
            "source_urls": ["https://example.com/story"],
            "body_markdown": "# Heading\n\nBody text.",
        }
        (content_dir / "published").mkdir()
        (content_dir / "published" / "sample-briefing.json").write_text(json.dumps(article), encoding="utf-8")

        build_site(content_dir, templates_dir, site_dir, state)
        first_digest = _digest_tree(site_dir)

        build_site(content_dir, templates_dir, site_dir, state)
        second_digest = _digest_tree(site_dir)

    assert first_digest == second_digest
    assert (site_dir / "index.html").exists()
    assert (site_dir / "status.html").exists()


def test_build_site_generates_sections_rss_and_sitemap(tmp_path):
    content_dir = tmp_path / "content"
    templates_dir = tmp_path / "templates"
    site_dir = tmp_path / "site"
    for directory in (content_dir / "published", content_dir / "queue", content_dir / "rejected", templates_dir):
        directory.mkdir(parents=True)

    with StateStore(tmp_path / "state.db") as state:
        state.initialize()
        state.record_published_index(
            slug="sample-briefing",
            title="Sample Briefing",
            content_type="latest_briefing",
            source_urls=["https://example.com/story"],
            published_at="2026-07-06T18:00:00Z",
        )
        state.record_published_index(
            slug="youtube-analysis",
            title="YouTube Analysis",
            content_type="youtube_intel",
            source_urls=["https://youtube.com/watch?v=test"],
            published_at="2026-07-06T19:00:00Z",
        )

        published_dir = content_dir / "published"
        published_dir.joinpath("sample-briefing.json").write_text(
            json.dumps(
                {
                    "slug": "sample-briefing",
                    "title": "Sample Briefing",
                    "dek": "Summary",
                    "content_type": "latest_briefing",
                    "published_at": "2026-07-06T18:00:00Z",
                    "confidence": "high",
                    "source_urls": ["https://example.com/story"],
                    "claim_labels": ["confirmed_fact"],
                    "body_markdown": "# Heading\n\nBody text.",
                }
            ),
            encoding="utf-8",
        )
        published_dir.joinpath("youtube-analysis.json").write_text(
            json.dumps(
                {
                    "slug": "youtube-analysis",
                    "title": "YouTube Analysis",
                    "dek": "Video summary",
                    "content_type": "youtube_intel",
                    "published_at": "2026-07-06T19:00:00Z",
                    "confidence": "medium",
                    "source_urls": ["https://youtube.com/watch?v=test"],
                    "claim_labels": ["reported_claim", "analysis"],
                    "body_markdown": "Transcript excerpt.",
                }
            ),
            encoding="utf-8",
        )
        (content_dir / "queue" / "queued.json").write_text("{}", encoding="utf-8")
        (content_dir / "rejected" / "rejected.json").write_text("{}", encoding="utf-8")

        build_site(content_dir, templates_dir, site_dir, state)

    assert (site_dir / "sections" / "index.html").exists()
    assert (site_dir / "sections" / "latest_briefing.html").exists()
    assert (site_dir / "sections" / "youtube_intel.html").exists()
    assert (site_dir / "rss.xml").exists()
    assert (site_dir / "sitemap.xml").exists()

    index_html = (site_dir / "index.html").read_text(encoding="utf-8")
    assert "Sections" in index_html
    assert "Latest Briefing" in index_html
    assert "YouTube Intel" in index_html

    article_html = (site_dir / "articles" / "youtube-analysis.html").read_text(encoding="utf-8")
    assert "confidence-badge" in article_html
    assert "Sources" in article_html
    assert "claim-labels" in article_html
    assert "https://youtube.com/watch?v=test" in article_html

    section_html = (site_dir / "sections" / "youtube_intel.html").read_text(encoding="utf-8")
    assert "YouTube Analysis" in section_html
    assert "claim_labels" not in section_html

    rss_xml = (site_dir / "rss.xml").read_text(encoding="utf-8")
    assert "<rss" in rss_xml
    assert "Sample Briefing" in rss_xml
    assert "/articles/sample-briefing.html" in rss_xml

    sitemap_xml = (site_dir / "sitemap.xml").read_text(encoding="utf-8")
    assert "<urlset" in sitemap_xml
    assert "/sections/latest_briefing.html" in sitemap_xml
    assert "/articles/youtube-analysis.html" in sitemap_xml
    assert "/rss.xml" in sitemap_xml

    status_html = (site_dir / "status.html").read_text(encoding="utf-8")
    assert "Queued items: 1" in status_html
    assert "Rejected items: 1" in status_html


def test_build_site_generates_youtube_channel_dashboard(tmp_path):
    content_dir = tmp_path / "content"
    templates_dir = tmp_path / "templates"
    site_dir = tmp_path / "site"
    for directory in (
        content_dir / "published",
        content_dir / "registry",
        tmp_path / "data" / "source-packets",
        tmp_path / "data" / "downloads" / "abc123",
        templates_dir,
    ):
        directory.mkdir(parents=True)

    (content_dir / "registry" / "youtube_channels.json").write_text(
        json.dumps(
            [
                {
                    "id": "channel-1",
                    "name": "Example UFO Channel",
                    "url": "https://www.youtube.com/@example",
                    "category": "uap_research",
                    "priority": 1,
                    "active": True,
                    "reason": "Useful transcript-driven interviews.",
                }
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "data" / "source-packets" / "example.json").write_text(
        json.dumps(
            {
                "source_type": "youtube",
                "registry_channel_id": "channel-1",
                "source_name": "Example UFO Channel",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Example Interview",
                "published_at": "2026-07-06T18:00:00Z",
                "status": "downloaded",
                "video_id": "abc123",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "data" / "downloads" / "abc123" / "metadata.json").write_text(
        json.dumps(
            {
                "video_id": "abc123",
                "status": "transcribed",
                "title": "Example Interview",
                "source_url": "https://www.youtube.com/watch?v=abc123",
            }
        ),
        encoding="utf-8",
    )

    with StateStore(tmp_path / "state.db") as state:
        state.initialize()
        build_site(content_dir, templates_dir, site_dir, state)

    dashboard_html = (site_dir / "youtube" / "index.html").read_text(encoding="utf-8")
    assert "Example UFO Channel" in dashboard_html
    assert "Useful transcript-driven interviews." in dashboard_html
    assert "Example Interview" in dashboard_html
    assert "1 transcript" in dashboard_html
    assert "1 download" in dashboard_html

    index_html = (site_dir / "index.html").read_text(encoding="utf-8")
    assert "/youtube/index.html" in index_html

    sitemap_xml = (site_dir / "sitemap.xml").read_text(encoding="utf-8")
    assert "/youtube/index.html" in sitemap_xml


def test_build_site_removes_stale_generated_pages(tmp_path):
    content_dir = tmp_path / "content"
    templates_dir = tmp_path / "templates"
    site_dir = tmp_path / "site"
    published_dir = content_dir / "published"
    published_dir.mkdir(parents=True)
    templates_dir.mkdir()

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

    with StateStore(tmp_path / "state.db") as state:
        state.initialize()
        build_site(content_dir, templates_dir, site_dir, state)
        (published_dir / "sample-briefing.json").unlink()
        build_site(content_dir, templates_dir, site_dir, state)

    assert not (site_dir / "articles" / "sample-briefing.html").exists()
    assert not (site_dir / "sections" / "latest_briefing.html").exists()
