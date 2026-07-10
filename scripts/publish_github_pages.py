from __future__ import annotations

from pathlib import Path

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.publish import publish_site


def main(root: Path | None = None) -> int:
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    result = publish_site(root)
    return 0 if result.result in {"success", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
