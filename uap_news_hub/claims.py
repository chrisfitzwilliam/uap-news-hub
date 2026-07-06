from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .utils import ensure_parent, utc_now


def merge_claim_record(claim_path: Path, article_claim: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    current: dict[str, Any] = {}
    if claim_path.exists():
        current = json.loads(claim_path.read_text(encoding="utf-8"))
    timestamp = now or utc_now()

    evidence = current.get("evidence", [])
    new_evidence = {
        "date": timestamp[:10],
        "source_url": article_claim["source_url"],
        "evidence_type": article_claim.get("label", "unverified"),
        "effect": article_claim.get("effect", "context"),
        "note": article_claim.get("note", ""),
    }
    if new_evidence not in evidence:
        evidence.append(new_evidence)

    assessment_history = current.get("assessment_history", [])
    confidence = article_claim.get("confidence", current.get("confidence", "low"))
    if not assessment_history or assessment_history[-1].get("confidence") != confidence:
        assessment_history.append(
            {
                "date": timestamp[:10],
                "confidence": confidence,
                "reason": article_claim.get("reason", "Updated from validated article."),
            }
        )

    merged = {
        "claim_id": current.get("claim_id") or article_claim["claim_id"],
        "topic": current.get("topic") or article_claim.get("topic", ""),
        "statement": current.get("statement") or article_claim.get("statement", ""),
        "status": current.get("status", "open"),
        "confidence": confidence,
        "first_reported_at": current.get("first_reported_at", timestamp),
        "last_updated_at": timestamp,
        "evidence": evidence,
        "related_articles": sorted(set(current.get("related_articles", []) + [article_claim["article_slug"]])),
        "assessment_history": assessment_history,
    }
    ensure_parent(claim_path)
    claim_path.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
    return merged

