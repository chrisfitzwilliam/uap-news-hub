from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .utils import ensure_parent, utc_now


def append_source_change(
    path: Path,
    *,
    action: str,
    source_type: str,
    source_id: str,
    reason: str,
    evidence_urls: list[str],
    agy_run_id: str | None = None,
    timestamp: str | None = None,
) -> None:
    ensure_parent(path)
    record = {
        "timestamp": timestamp or utc_now(),
        "action": action,
        "source_type": source_type,
        "source_id": source_id,
        "reason": reason,
        "evidence_urls": evidence_urls,
        "agy_run_id": agy_run_id,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def load_registry(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def deactivate_after_failures(source: dict[str, Any], threshold: int = 10) -> bool:
    failures = int(source.get("consecutive_failures", 0))
    if failures >= threshold:
        source["active"] = False
        return True
    return False

