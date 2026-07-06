import json
from pathlib import Path
from urllib.error import HTTPError

from uap_news_hub.ingest import ingest_registry_file
from uap_news_hub.state import StateStore


RSS_FIXTURE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>First item</title>
      <link>https://example.com/story?utm_source=newsletter</link>
      <guid>https://example.com/story?utm_source=newsletter</guid>
      <pubDate>Mon, 06 Jul 2026 18:00:00 GMT</pubDate>
      <description>Example summary</description>
    </item>
  </channel>
</rss>
"""

RSS_FIXTURE_TWO_ITEMS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>First item</title>
      <link>https://example.com/story-1</link>
      <guid>https://example.com/story-1</guid>
      <pubDate>Mon, 06 Jul 2026 18:00:00 GMT</pubDate>
      <description>Example summary 1</description>
    </item>
    <item>
      <title>Second item</title>
      <link>https://example.com/story-2</link>
      <guid>https://example.com/story-2</guid>
      <pubDate>Mon, 06 Jul 2026 19:00:00 GMT</pubDate>
      <description>Example summary 2</description>
    </item>
  </channel>
</rss>
"""


def test_ingest_registry_writes_source_packets_and_dedups_second_run(tmp_path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "news_sources.json").write_text(
        json.dumps(
            [
                {
                    "id": "example-news",
                    "name": "Example News",
                    "url": "https://example.com/feed",
                    "active": True,
                    "priority": 1,
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    packets_dir = tmp_path / "source-packets"
    packets_dir.mkdir()
    with StateStore(tmp_path / "state.db") as store:
        store.initialize()

        fetch_calls = []

        def fetcher(source):
            fetch_calls.append(source["id"])
            return RSS_FIXTURE, {"etag": "abc", "last_modified": "Mon, 06 Jul 2026 18:00:00 GMT"}

        first_run = ingest_registry_file(registry_dir / "news_sources.json", store, packets_dir, fetcher=fetcher)
        second_run = ingest_registry_file(registry_dir / "news_sources.json", store, packets_dir, fetcher=fetcher)

        assert len(first_run) == 1
        assert second_run == []
        assert fetch_calls == ["example-news", "example-news"]
        assert len(list(packets_dir.glob("*.json"))) == 1


def test_fetch_registry_feed_sends_conditional_headers(tmp_path):
    from uap_news_hub.ingest import fetch_registry_feed

    captured = {}

    class FakeResponse:
        status = 200

        def __init__(self, body: str):
            self._body = body
            self.headers = {"ETag": "abc123", "Last-Modified": "Mon, 06 Jul 2026 18:00:00 GMT"}

        def read(self):
            return self._body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def opener(request, timeout=0):
        captured["url"] = request.full_url
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        return FakeResponse("<rss><channel></channel></rss>")

    body, headers = fetch_registry_feed(
        {
            "url": "https://example.com/channel",
            "rss_url": "https://example.com/feed",
            "etag": "prev-etag",
            "last_modified": "old-time",
        },
        opener=opener,
    )

    assert body.startswith("<rss")
    assert captured["url"] == "https://example.com/feed"
    assert captured["headers"]["if-none-match"] == "prev-etag"
    assert captured["headers"]["if-modified-since"] == "old-time"
    assert headers["etag"] == "abc123"
    assert headers["last_modified"] == "Mon, 06 Jul 2026 18:00:00 GMT"


def test_fetch_registry_feed_retries_transient_error(tmp_path):
    from uap_news_hub.ingest import fetch_registry_feed

    attempts = []
    sleeps = []

    class FakeResponse:
        status = 200

        def __init__(self):
            self.headers = {}

        def read(self):
            return b"<rss><channel></channel></rss>"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def opener(request, timeout=0):
        attempts.append(request.full_url)
        if len(attempts) == 1:
            raise HTTPError(request.full_url, 429, "Too Many Requests", hdrs=None, fp=None)
        return FakeResponse()

    body, headers = fetch_registry_feed(
        {"url": "https://example.com/feed"},
        opener=opener,
        sleep=sleeps.append,
        max_attempts=2,
        retry_delay_seconds=2,
    )

    assert body.startswith("<rss")
    assert headers["status"] == "200"
    assert len(attempts) == 2
    assert sleeps == [2]


def test_ingest_sources_main_uses_fetcher_and_writes_packets(tmp_path, monkeypatch):
    root = tmp_path
    registry_dir = root / "content" / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "news_sources.json").write_text(
        json.dumps(
            [
                {
                    "id": "example-news",
                    "name": "Example News",
                    "url": "https://example.com/feed",
                    "active": True,
                    "priority": 1,
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    packets_dir = root / "data" / "source-packets"

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from ingest_sources import main as ingest_sources_main

    def fetcher(source):
        assert source["url"] == "https://example.com/feed"
        return RSS_FIXTURE, {"etag": "abc"}

    exit_code = ingest_sources_main(root, fetcher=fetcher)

    assert exit_code == 0
    assert len(list(packets_dir.glob("*.json"))) == 1


def test_ingest_sources_main_reads_youtube_registry_file(tmp_path, monkeypatch):
    root = tmp_path
    registry_dir = root / "content" / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "youtube_channels.json").write_text(
        json.dumps(
            [
                {
                    "id": "example-youtube",
                    "name": "Example YouTube",
                    "url": "https://www.youtube.com/@example",
                    "rss_url": "https://example.com/feed",
                    "active": True,
                    "priority": 1,
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    packets_dir = root / "data" / "source-packets"

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from ingest_sources import main as ingest_sources_main

    def fetcher(source):
        assert source["rss_url"] == "https://example.com/feed"
        return RSS_FIXTURE, {"etag": "abc"}

    exit_code = ingest_sources_main(root, fetcher=fetcher)

    assert exit_code == 0
    packets = list(packets_dir.glob("*.json"))
    assert len(packets) == 1
    packet = json.loads(packets[0].read_text(encoding="utf-8"))
    assert packet["source_type"] == "youtube"


def test_ingest_registry_persists_conditional_headers(tmp_path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    registry_path = registry_dir / "news_sources.json"
    registry_path.write_text(
        json.dumps(
            [
                {
                    "id": "example-news",
                    "name": "Example News",
                    "url": "https://example.com/feed",
                    "active": True,
                    "priority": 1,
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    packets_dir = tmp_path / "source-packets"
    with StateStore(tmp_path / "state.db") as store:
        store.initialize()

        def fetcher(source):
            return RSS_FIXTURE, {"etag": "abc123", "last_modified": "Mon, 06 Jul 2026 18:00:00 GMT"}

        ingest_registry_file(registry_path, store, packets_dir, fetcher=fetcher)

        updated_registry = json.loads(registry_path.read_text(encoding="utf-8"))
        source = updated_registry[0]
        assert source["etag"] == "abc123"
        assert source["last_modified"] == "Mon, 06 Jul 2026 18:00:00 GMT"
        assert source["last_checked_at"]


def test_ingest_registry_records_fetch_failure_and_deactivates(tmp_path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    registry_path = registry_dir / "news_sources.json"
    registry_path.write_text(
        json.dumps(
            [
                {
                    "id": "example-news",
                    "name": "Example News",
                    "url": "https://example.com/feed",
                    "active": True,
                    "priority": 1,
                    "consecutive_failures": 9,
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    packets_dir = tmp_path / "source-packets"
    with StateStore(tmp_path / "state.db") as store:
        store.initialize()

        def fetcher(source):
            raise RuntimeError("feed unavailable")

        ingest_registry_file(registry_path, store, packets_dir, fetcher=fetcher)

        updated_registry = json.loads(registry_path.read_text(encoding="utf-8"))
        source = updated_registry[0]
        assert source["consecutive_failures"] == 10
        assert source["active"] is False
        assert not list(packets_dir.glob("*.json"))


def test_ingest_registry_honors_packet_cap(tmp_path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    registry_path = registry_dir / "news_sources.json"
    registry_path.write_text(
        json.dumps(
            [
                {
                    "id": "example-news",
                    "name": "Example News",
                    "url": "https://example.com/feed",
                    "active": True,
                    "priority": 1,
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    packets_dir = tmp_path / "source-packets"
    with StateStore(tmp_path / "state.db") as store:
        store.initialize()

        def fetcher(source):
            return RSS_FIXTURE_TWO_ITEMS, {"etag": "abc"}

        packets = ingest_registry_file(
            registry_path,
            store,
            packets_dir,
            fetcher=fetcher,
            max_packets=1,
        )

        assert len(packets) == 1
        assert len(list(packets_dir.glob("*.json"))) == 1


def test_ingest_sources_main_respects_env_packet_cap(tmp_path, monkeypatch):
    root = tmp_path
    registry_dir = root / "content" / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "news_sources.json").write_text(
        json.dumps(
            [
                {
                    "id": "example-news",
                    "name": "Example News",
                    "url": "https://example.com/feed",
                    "active": True,
                    "priority": 1,
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    packets_dir = root / "data" / "source-packets"

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from ingest_sources import main as ingest_sources_main

    def fetcher(source):
        return RSS_FIXTURE_TWO_ITEMS, {"etag": "abc"}

    monkeypatch.setenv("UAP_INGEST_MAX_PACKETS", "1")
    exit_code = ingest_sources_main(root, fetcher=fetcher)

    assert exit_code == 0
    assert len(list(packets_dir.glob("*.json"))) == 1
