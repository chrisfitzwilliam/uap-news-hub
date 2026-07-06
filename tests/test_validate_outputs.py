import json
from pathlib import Path

from uap_news_hub.state import StateStore
from uap_news_hub.validation import validate_article_payload


def test_validate_article_rejects_missing_source_url_and_duplicate_source(tmp_path):
    db_path = tmp_path / "state.db"
    with StateStore(db_path) as store:
        store.initialize()
        store.record_published_index(
            slug="existing-article",
            title="Existing Article",
            content_type="latest_briefing",
            source_urls=["https://example.com/story"],
            published_at="2026-07-06T18:00:00Z",
        )

        bad_payload = {
            "slug": "new-article",
            "title": "New Article",
            "content_type": "latest_briefing",
            "source_urls": [],
            "confidence": "high",
            "body_markdown": "Body",
            "review_result": "pass",
        }
        result = validate_article_payload(bad_payload, store)
        assert not result.passed
        assert "source_url" in " ".join(result.errors)

        duplicate_payload = {
            "slug": "new-article-2",
            "title": "New Article 2",
            "content_type": "latest_briefing",
            "source_urls": ["https://example.com/story?utm_source=x"],
            "confidence": "high",
            "body_markdown": "Body",
            "review_result": "pass",
        }
        duplicate_result = validate_article_payload(duplicate_payload, store)
        assert not duplicate_result.passed
        assert "already published" in " ".join(duplicate_result.errors)


def test_validate_article_rejects_long_quotes_and_bad_timestamps(tmp_path):
    db_path = tmp_path / "state.db"
    with StateStore(db_path) as store:
        store.initialize()

        payload = {
            "slug": "quoted-article",
            "title": "Quoted Article",
            "content_type": "youtube_intel",
            "source_urls": ["https://example.com/story"],
            "confidence": "medium",
            "body_markdown": "Body",
            "review_result": "pass",
            "video_duration_seconds": 60,
            "claims": [
                {
                    "quote": " ".join(["word"] * 76),
                    "speaker": "SPEAKER_00",
                    "timestamp_start": "00:01:10",
                    "timestamp_end": "00:00:50",
                }
            ],
        }

        result = validate_article_payload(payload, store)

        assert not result.passed
        joined = " ".join(result.errors)
        assert "quote exceeds 75 words" in joined or "direct transcript quote exceeds 75 words" in joined
        assert "timestamp_end must be after timestamp_start" in joined


def test_validate_outputs_main_fails_closed_on_invalid_json(tmp_path, monkeypatch, capsys):
    root = tmp_path
    published_dir = root / "content" / "published"
    published_dir.mkdir(parents=True)
    (published_dir / "broken.json").write_text("{not valid json", encoding="utf-8")

    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))

    from validate_outputs import main as validate_outputs_main

    exit_code = validate_outputs_main(root)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "broken.json" in captured.out
    assert (root / "data" / "validation" / "broken.json").exists()


def test_validate_outputs_main_validates_queue_and_published_content(tmp_path, monkeypatch):
    root = tmp_path
    published_dir = root / "content" / "published"
    queue_dir = root / "content" / "queue"
    published_dir.mkdir(parents=True)
    queue_dir.mkdir(parents=True)
    (root / "templates").mkdir()
    with StateStore(root / "data" / "state.db") as store:
        store.initialize()
        store.record_published_index(
            slug="existing-article",
            title="Existing Article",
            content_type="latest_briefing",
            source_urls=["https://example.com/story"],
            published_at="2026-07-06T18:00:00Z",
        )

    published_payload = {
        "slug": "new-article",
        "title": "New Article",
        "content_type": "latest_briefing",
        "source_urls": ["https://example.com/story-2"],
        "confidence": "high",
        "body_markdown": "Body",
        "review_result": "pass",
    }
    queue_payload = {
        "slug": "queued-article",
        "title": "Queued Article",
        "content_type": "youtube_intel",
        "source_urls": ["https://example.com/story-3"],
        "confidence": "medium",
        "body_markdown": "Queued body",
        "review_result": "reject",
    }
    (published_dir / "new-article.json").write_text(json.dumps(published_payload), encoding="utf-8")
    (queue_dir / "queued-article.json").write_text(json.dumps(queue_payload), encoding="utf-8")

    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))

    from validate_outputs import main as validate_outputs_main

    exit_code = validate_outputs_main(root)

    assert exit_code == 0
    assert (root / "data" / "validation" / "new-article.json").exists()
    assert (root / "data" / "validation" / "queued-article.json").exists()


def test_validate_outputs_main_rejects_queue_item_marked_for_publish(tmp_path, monkeypatch, capsys):
    root = tmp_path
    queue_dir = root / "content" / "queue"
    queue_dir.mkdir(parents=True)
    (root / "templates").mkdir()
    with StateStore(root / "data" / "state.db") as store:
        store.initialize()

    queue_payload = {
        "slug": "queued-article",
        "title": "Queued Article",
        "content_type": "youtube_intel",
        "source_urls": ["https://example.com/story-3"],
        "confidence": "medium",
        "body_markdown": "Queued body",
        "review_result": "pass",
    }
    (queue_dir / "queued-article.json").write_text(json.dumps(queue_payload), encoding="utf-8")

    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))

    from validate_outputs import main as validate_outputs_main

    exit_code = validate_outputs_main(root)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "queue/queued-article.json" in captured.out
    assert "review_result" in captured.out
    assert (root / "data" / "validation" / "queued-article.json").exists()
