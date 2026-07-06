from __future__ import annotations

import os
import sys

from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from uap_news_hub.environment import check_environment


def main() -> int:
    result = check_environment(env=dict(os.environ))
    for error in result.errors:
        print(error)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
