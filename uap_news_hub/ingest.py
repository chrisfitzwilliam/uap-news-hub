from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import time

from .state import StateStore
from .registry import deactivate_after_failures
from .urls import item_key_for_url, normalize_url
from .utils import ensure_parent, slugify, utc_now, write_json


def load_registry(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_feed_entries(feed_xml: str) -> list[dict[str, str]]:
    root = ET.fromstring(feed_xml)
    root_name = _local_name(root.tag)
    entries: list[dict[str, str]] = []

    if root_name == "rss":
        channel = next((child for child in root if _local_name(child.tag) == "channel"), None)
        if channel is None:
            return entries
        for item in channel:
            if _local_name(item.tag) != "item":
                continue
            fields = { _local_name(child.tag): (child.text or "").strip() for child in item }
            entries.append(fields)
        return entries

    if root_name == "feed":
        for entry in root:
            if _local_name(entry.tag) != "entry":
                continue
            fields = {_local_name(child.tag): (child.text or "").strip() for child in entry}
            link = ""
            for child in entry:
                if _local_name(child.tag) == "link":
                    link = child.attrib.get("href", "")
                    break
            if link and "link" not in fields:
                fields["link"] = link
            entries.append(fields)
    return entries


def _source_type_from_registry(path: Path) -> str:
    stem = path.stem
    if stem.endswith("_sources"):
        return stem[: -len("_sources")]
    if stem.endswith("_channels"):
        return stem[: -len("_channels")]
    return stem


def _packet_id(source_type: str, title: str, item_key: str) -> str:
    digest = hashlib.sha1(item_key.encode("utf-8")).hexdigest()[:10]
    return f"{source_type}-{slugify(title)}-{digest}"


def fetch_registry_feed(
    source: dict[str, Any],
    *,
    opener: Callable[..., Any] = urlopen,
    sleep: Callable[[float], None] = time.sleep,
    timeout_seconds: int = 30,
    max_attempts: int = 3,
    retry_delay_seconds: float = 2.0,
) -> tuple[str, dict[str, str | None]]:
    url = source.get("rss_url") or source.get("url")
    if not url:
        raise ValueError("source is missing url/rss_url")

    headers: dict[str, str] = {
        "User-Agent": "UAPNewsHub/1.0 (local pipeline)",
    }
    if source.get("etag"):
        headers["If-None-Match"] = str(source["etag"])
    if source.get("last_modified"):
        headers["If-Modified-Since"] = str(source["last_modified"])

    request = Request(str(url), headers=headers)
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with opener(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                response_headers = getattr(response, "headers", {})
                return body, {
                    "status": str(getattr(response, "status", 200)),
                    "etag": response_headers.get("ETag") or response_headers.get("etag"),
                    "last_modified": response_headers.get("Last-Modified") or response_headers.get("last-modified"),
                }
        except HTTPError as exc:
            if exc.code == 304:
                return "", {
                    "status": "304",
                    "etag": exc.headers.get("ETag") if exc.headers else None,
                    "last_modified": exc.headers.get("Last-Modified") if exc.headers else None,
                }
            if exc.code < 500 and exc.code != 429:
                raise
            last_error = exc
        except Exception as exc:
            last_error = exc

        if attempt < max_attempts:
            sleep(retry_delay_seconds * attempt)

    if last_error is not None:
        raise last_error
    raise RuntimeError("fetch_registry_feed failed without an exception")


def ingest_registry_file(
    registry_path: Path,
    store: StateStore,
    packets_dir: Path,
    *,
    fetcher: Callable[[dict[str, Any]], tuple[str, dict[str, str] | None]] | None = None,
    max_packets: int | None = None,
) -> list[dict[str, Any]]:
    sources = load_registry(registry_path)
    source_type = _source_type_from_registry(registry_path)
    results: list[dict[str, Any]] = []
    packets_dir.mkdir(parents=True, exist_ok=True)
    registry_dirty = False
    packet_count = 0

    for source in sources:
        if max_packets is not None and packet_count >= max_packets:
            break
        if not source.get("active", True):
            continue
        if fetcher is None:
            raise RuntimeError("No fetcher provided for ingestion")
        try:
            feed_text, headers = fetcher(source)
        except Exception:
            source["last_checked_at"] = utc_now()
            source["consecutive_failures"] = int(source.get("consecutive_failures", 0)) + 1
            deactivate_after_failures(source)
            registry_dirty = True
            continue
        source["last_checked_at"] = utc_now()
        source["consecutive_failures"] = 0
        if headers:
            if headers.get("etag") is not None:
                source["etag"] = headers.get("etag")
            if headers.get("last_modified") is not None:
                source["last_modified"] = headers.get("last_modified")
            registry_dirty = True
        entries = _parse_feed_entries(feed_text)
        for entry in entries:
            link = entry.get("link") or entry.get("guid") or entry.get("id")
            if not link:
                continue
            source_url = normalize_url(link)
            item_key = item_key_for_url(link)
            seen = store.get_seen_item(item_key)
            if seen:
                continue
            title = entry.get("title") or source.get("name") or "Untitled"
            packet = {
                "packet_id": _packet_id(source_type, title, source_url),
                "source_type": source_type,
                "source_name": source.get("name", ""),
                "source_url": source_url,
                "title": title,
                "published_at": entry.get("pubDate") or entry.get("updated") or utc_now(),
                "collected_at": utc_now(),
                "author_or_channel": entry.get("author") or source.get("name", ""),
                "raw_summary": entry.get("description") or entry.get("summary") or "",
                "candidate_reason": f"New item from monitored {source_type} source.",
                "related_urls": [],
                "status": "new",
                "raw_feed_headers": headers or {},
            }
            write_json(packets_dir / f"{packet['packet_id']}.json", packet)
            store.record_seen_item(
                item_key,
                source_type,
                "new",
                source_url=source_url,
                title=title,
                metadata={"packet_id": packet["packet_id"], "source_id": source.get("id")},
            )
            results.append(packet)
            packet_count += 1
            if max_packets is not None and packet_count >= max_packets:
                break
        registry_dirty = True
        if max_packets is not None and packet_count >= max_packets:
            break
    if registry_dirty:
        write_json(registry_path, sources)
    return results
