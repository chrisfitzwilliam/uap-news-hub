from __future__ import annotations

import os
from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.youtube_pipeline import transcribe_downloads


def main(
    root: Path | None = None,
    *,
    max_items: int | None = None,
    transcriber=None,
) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    if max_items is None:
        raw_max_items = os.environ.get("UAP_TRANSCRIPT_LIMIT", "").strip()
        if raw_max_items:
            max_items = int(raw_max_items)
    kwargs = {"max_items": max_items}
    if transcriber is not None:
        kwargs["transcriber"] = transcriber
    outcomes = transcribe_downloads(root, **kwargs)
    return 0 if all(outcome.status == "transcribed" for outcome in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
