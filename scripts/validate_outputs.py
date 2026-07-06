from __future__ import annotations

from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.state import StateStore
from uap_news_hub.validation import validate_all_content


def main(root: Path | None = None) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    with StateStore(root / "data" / "state.db") as state:
        state.initialize()
        result = validate_all_content(root / "content", state)
        for error in result.errors:
            print(error)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
