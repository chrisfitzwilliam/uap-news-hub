from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.source_triage import run_source_triage_pipeline


def main(root: Path | None = None, *, budget_limit: int | None = None) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    run_source_triage_pipeline(root, budget_limit=budget_limit)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--budget-limit", type=int, default=None)
    args = parser.parse_args()
    raise SystemExit(main(args.root, budget_limit=args.budget_limit))
