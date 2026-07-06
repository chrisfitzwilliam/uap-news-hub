from __future__ import annotations

from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.media import cleanup_transcript_audio


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cleanup_transcript_audio(root / "data" / "downloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
