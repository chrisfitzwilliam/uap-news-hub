import json
from pathlib import Path

from uap_news_hub.pipeline import run_site_pipeline
from uap_news_hub.state import StateStore


def test_run_site_pipeline_validates_builds_and_records_run(tmp_path):
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

    result = run_site_pipeline(tmp_path, run_type="hourly")

    assert result.result == "success"
    assert (site_dir / "index.html").exists()
    assert (site_dir / "status.html").exists()

    with StateStore(tmp_path / "data" / "state.db") as state:
        state.initialize()
        run = state.latest_run("hourly")
        assert run is not None
        assert run["result"] == "success"


def test_run_hourly_main_ingests_before_building(tmp_path, monkeypatch):
    root = tmp_path
    content_dir = root / "content" / "published"
    content_dir.mkdir(parents=True)
    (root / "templates").mkdir()

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
    (content_dir / "sample-briefing.json").write_text(json.dumps(article), encoding="utf-8")

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from run_hourly import main as run_hourly_main

    events = []

    def ingest(root_arg):
        events.append(("ingest", Path(root_arg)))
        return 0

    exit_code = run_hourly_main(root, ingest=ingest)

    assert exit_code == 0
    assert events == [("ingest", root)]
    assert (root / "site" / "index.html").exists()


def test_run_daily_main_ingests_downloads_and_transcribes_before_building(tmp_path, monkeypatch):
    root = tmp_path
    content_dir = root / "content" / "published"
    content_dir.mkdir(parents=True)
    (root / "templates").mkdir()

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
    (content_dir / "sample-briefing.json").write_text(json.dumps(article), encoding="utf-8")

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from run_daily import main as run_daily_main

    events = []

    def ingest(root_arg):
        events.append(("ingest", Path(root_arg)))
        return 0

    def triage(root_arg, **kwargs):
        events.append(("triage", Path(root_arg)))
        return type("Result", (), {"agy_calls": 1})()

    def download(root_arg):
        events.append(("download", Path(root_arg)))
        return 0

    def transcribe(root_arg):
        events.append(("transcribe", Path(root_arg)))
        return 0

    def editorial(root_arg, **kwargs):
        events.append(("editorial", Path(root_arg)))
        return type("Result", (), {"agy_calls": 0})()

    exit_code = run_daily_main(root, update_youtube=lambda: None, ingest=ingest, triage=triage, download=download, transcribe=transcribe, editorial=editorial)

    assert exit_code == 0
    assert events == [("ingest", root), ("triage", root), ("download", root), ("transcribe", root), ("editorial", root)]
    assert (root / "site" / "index.html").exists()


def test_run_daily_main_uses_structured_triage_result_with_default_import(tmp_path, monkeypatch):
    root = tmp_path
    content_dir = root / "content" / "published"
    content_dir.mkdir(parents=True)
    (root / "templates").mkdir()

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
    (content_dir / "sample-briefing.json").write_text(json.dumps(article), encoding="utf-8")

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import run_daily

    events = []

    def ingest(root_arg):
        events.append(("ingest", Path(root_arg)))
        return 0

    def download(root_arg):
        events.append(("download", Path(root_arg)))
        return 0

    def transcribe(root_arg):
        events.append(("transcribe", Path(root_arg)))
        return 0

    def editorial(root_arg, **kwargs):
        events.append(("editorial", Path(root_arg), kwargs["budget_limit"]))
        return type("Result", (), {"agy_calls": 0})()

    monkeypatch.setattr(
        run_daily,
        "run_source_triage_pipeline",
        lambda root_arg, **kwargs: type("Result", (), {"agy_calls": 2})(),
    )

    exit_code = run_daily.main(root, update_youtube=lambda: None, ingest=ingest, download=download, transcribe=transcribe, editorial=editorial)

    assert exit_code == 0
    assert events == [
        ("ingest", root),
        ("download", root),
        ("transcribe", root),
        ("editorial", root, 23),
    ]


def test_run_site_pipeline_records_agy_call_count(tmp_path):
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

    result = run_site_pipeline(tmp_path, run_type="daily", agy_calls=7)

    assert result.result == "success"
    assert (site_dir / "index.html").exists()

    with StateStore(tmp_path / "data" / "state.db") as state:
        state.initialize()
        run = state.latest_run("daily")
        assert run is not None
        assert run["agy_calls"] == 7
