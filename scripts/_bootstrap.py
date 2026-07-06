from __future__ import annotations

import sys
from pathlib import Path


def add_repo_root_to_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root

