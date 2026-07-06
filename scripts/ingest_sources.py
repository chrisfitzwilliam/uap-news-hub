from __future__ import annotations

import os
from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.ingest import fetch_registry_feed, ingest_registry_file
from uap_news_hub.state import StateStore


def main(root: Path | None = None, *, fetcher=fetch_registry_feed, max_packets: int | None = None) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    if max_packets is None:
        raw_max_packets = os.environ.get("UAP_INGEST_MAX_PACKETS", "").strip()
        if raw_max_packets:
            max_packets = int(raw_max_packets)
    registry_dir = root / "content" / "registry"
    packets_dir = root / "data" / "source-packets"
    registry_files = {registry_dir / "youtube_channels.json", *registry_dir.glob("*_sources.json")}
    registry_files = {path for path in registry_files if path.exists()}
    with StateStore(root / "data" / "state.db") as state:
        state.initialize()
        for registry_file in sorted(registry_files):
            ingest_registry_file(registry_file, state, packets_dir, fetcher=fetcher, max_packets=max_packets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
