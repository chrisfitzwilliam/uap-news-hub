from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.youtube_editorial import run_youtube_editorial_pipeline


def main(root: Path | None = None) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    run_youtube_editorial_pipeline(root)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.root))
