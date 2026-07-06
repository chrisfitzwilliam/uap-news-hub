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
