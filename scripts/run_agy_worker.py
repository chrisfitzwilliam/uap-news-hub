from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.agy import run_agy_worker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/agy-runs"))
    args = parser.parse_args()

    prompt_text = args.prompt.read_text(encoding="utf-8")
    result = run_agy_worker(prompt_text, save_dir=args.output_dir / "latest")
    print(result.parsed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
