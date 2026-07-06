from __future__ import annotations

from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.build import build_site
from uap_news_hub.state import StateStore


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with StateStore(root / "data" / "state.db") as state:
        state.initialize()
        build_site(root / "content", root / "templates", root / "site", state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
