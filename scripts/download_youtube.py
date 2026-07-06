from __future__ import annotations

import os
from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.youtube_pipeline import download_youtube_queue


def main(
    root: Path | None = None,
    *,
    max_items: int | None = None,
    downloader=None,
    sleep=None,
) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    if max_items is None:
        raw_max_items = os.environ.get("UAP_YOUTUBE_DOWNLOAD_LIMIT", "").strip()
        if raw_max_items:
            max_items = int(raw_max_items)
    kwargs = {"sleep": sleep or (lambda seconds: None), "max_items": max_items}
    if downloader is not None:
        kwargs["downloader"] = downloader
    outcomes = download_youtube_queue(root, **kwargs)
    return 0 if all(outcome.status == "downloaded" for outcome in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
