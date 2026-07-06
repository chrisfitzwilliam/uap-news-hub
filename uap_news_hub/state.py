from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .utils import ensure_parent, utc_now
from .urls import normalize_url


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS seen_items (
  item_key TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  status TEXT NOT NULL,
  source_url TEXT,
  title TEXT,
  metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS published_index (
  slug TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  content_type TEXT NOT NULL,
  source_urls TEXT NOT NULL,
  published_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_history (
  run_id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  result TEXT,
  agy_calls INTEGER DEFAULT 0,
  error_summary TEXT
);
"""


class StateStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        ensure_parent(self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def __enter__(self) -> "StateStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def initialize(self) -> None:
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def _fetch_one(self, query: str, params: Iterable[Any]) -> dict[str, Any] | None:
        cur = self.connection.execute(query, tuple(params))
        row = cur.fetchone()
        return dict(row) if row else None

    def record_seen_item(
        self,
        item_key: str,
        source_type: str,
        status: str,
        *,
        source_url: str | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
        first_seen_at: str | None = None,
    ) -> None:
        now = first_seen_at or utc_now()
        metadata_json = json.dumps(metadata or {}, sort_keys=True)
        self.connection.execute(
            """
            INSERT INTO seen_items (item_key, source_type, first_seen_at, status, source_url, title, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_key) DO UPDATE SET
                source_type=excluded.source_type,
                status=excluded.status,
                source_url=COALESCE(excluded.source_url, seen_items.source_url),
                title=COALESCE(excluded.title, seen_items.title),
                metadata_json=COALESCE(excluded.metadata_json, seen_items.metadata_json)
            """,
            (item_key, source_type, now, status, source_url, title, metadata_json),
        )
        self.connection.commit()

    def get_seen_item(self, item_key: str) -> dict[str, Any] | None:
        return self._fetch_one("SELECT * FROM seen_items WHERE item_key = ?", (item_key,))

    def record_published_index(
        self,
        *,
        slug: str,
        title: str,
        content_type: str,
        source_urls: list[str],
        published_at: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO published_index (slug, title, content_type, source_urls, published_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title=excluded.title,
                content_type=excluded.content_type,
                source_urls=excluded.source_urls,
                published_at=excluded.published_at
            """,
            (slug, title, content_type, json.dumps(source_urls, sort_keys=True), published_at),
        )
        self.connection.commit()

    def slug_exists(self, slug: str) -> bool:
        row = self._fetch_one("SELECT 1 FROM published_index WHERE slug = ?", (slug,))
        return row is not None

    def title_exists(self, title: str) -> bool:
        row = self._fetch_one("SELECT 1 FROM published_index WHERE lower(title) = lower(?)", (title,))
        return row is not None

    def published_source_urls(self) -> set[str]:
        rows = self.connection.execute("SELECT source_urls FROM published_index").fetchall()
        urls: set[str] = set()
        for row in rows:
            for url in json.loads(row["source_urls"]):
                urls.add(normalize_url(url))
        return urls

    def source_url_published(self, url: str) -> bool:
        return normalize_url(url) in self.published_source_urls()

    def record_run(
        self,
        *,
        run_id: str,
        run_type: str,
        started_at: str,
        finished_at: str | None = None,
        result: str | None = None,
        agy_calls: int = 0,
        error_summary: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO run_history (run_id, run_type, started_at, finished_at, result, agy_calls, error_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                finished_at=excluded.finished_at,
                result=excluded.result,
                agy_calls=excluded.agy_calls,
                error_summary=excluded.error_summary
            """,
            (run_id, run_type, started_at, finished_at, result, agy_calls, error_summary),
        )
        self.connection.commit()

    def latest_run(self, run_type: str) -> dict[str, Any] | None:
        return self._fetch_one(
            "SELECT * FROM run_history WHERE run_type = ? ORDER BY started_at DESC LIMIT 1",
            (run_type,),
        )
