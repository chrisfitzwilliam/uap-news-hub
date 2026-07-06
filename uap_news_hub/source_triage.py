from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .agy import AgyRunResult, run_agy_worker
from .state import StateStore
from .urls import item_key_for_url, normalize_url
from .utils import utc_now, write_json


TRIAGE_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "triage.schema.json"
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

ELIGIBLE_TRIAGE_STATUSES = {"new"}
DEFAULT_BATCH_SIZE = 10


@dataclass
class TriageOutcome:
    packet_id: str
    decision: str
    packet_path: Path
    triage_run_dir: Path
    call_count: int


@dataclass
class SourceTriageRunResult:
    outcomes: list[TriageOutcome]
    agy_calls: int
    budget_exhausted: bool


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _eligible_packet(packet: dict[str, Any]) -> bool:
    return str(packet.get("status", "new")) in ELIGIBLE_TRIAGE_STATUSES


def _load_prompt() -> str:
    prompt_path = PROMPTS_DIR / "source_triage.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return ""


def _render_prompt(packets: list[dict[str, Any]], published_source_urls: list[str]) -> str:
    context = {
        "published_source_urls": published_source_urls,
        "packets": packets,
    }
    parts = [_load_prompt(), "INPUT_JSON:", json.dumps(context, indent=2, sort_keys=True), "Return JSON only, no markdown fences, no preamble."]
    return "\n\n".join(part for part in parts if part)


def _validate_triage_item(item: dict[str, Any]) -> None:
    schema = json.loads(TRIAGE_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(item), key=lambda error: list(error.path))
    if errors:
        raise ValueError("; ".join(error.message for error in errors))


def _triage_run_dir(root: Path, batch_index: int) -> Path:
    return root / "data" / "agy-runs" / "latest" / "source-triage" / f"batch-{batch_index:03d}"


def _process_batch(
    root: Path,
    *,
    batch: list[Path],
    published_source_urls: list[str],
    runner: Callable[[str], AgyRunResult],
    batch_index: int,
    store: StateStore,
) -> SourceTriageRunResult:
    packets = [_load_json(packet_path) for packet_path in batch]
    prompt = _render_prompt(packets, published_source_urls)
    run_dir = _triage_run_dir(root, batch_index)
    result = runner(prompt, save_dir=run_dir)
    payload = result.parsed
    if not isinstance(payload, list):
        raise ValueError("source triage must return a JSON array")
    if len(payload) != len(packets):
        raise ValueError("source triage returned the wrong number of decisions")

    outcomes: list[TriageOutcome] = []
    for packet_path, packet, decision_item in zip(batch, packets, payload):
        if not isinstance(decision_item, dict):
            raise ValueError("source triage decisions must be JSON objects")
        _validate_triage_item(decision_item)
        packet_id = str(packet.get("packet_id") or packet_path.stem)
        if str(decision_item.get("packet_id")) != packet_id:
            raise ValueError("source triage decision packet_id mismatch")
        decision = str(decision_item.get("decision", "ignore"))
        packet["status"] = decision
        packet["triage"] = decision_item
        packet["triaged_at"] = utc_now()
        write_json(packet_path, packet)

        source_url = str(packet.get("source_url", ""))
        if source_url:
            store.record_seen_item(
                item_key_for_url(source_url),
                str(packet.get("source_type", "unknown")),
                decision,
                source_url=normalize_url(source_url),
                title=str(packet.get("title", "")),
                metadata={"packet_id": packet_id, "decision": decision},
            )

        outcomes.append(
            TriageOutcome(
                packet_id=packet_id,
                decision=decision,
                packet_path=packet_path,
                triage_run_dir=run_dir,
                call_count=result.call_count,
            )
        )

    return SourceTriageRunResult(outcomes=outcomes, agy_calls=result.call_count, budget_exhausted=False)


def run_source_triage_pipeline(
    root: Path,
    *,
    runner: Callable[[str], AgyRunResult] = run_agy_worker,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_items: int | None = None,
    budget_limit: int | None = None,
) -> SourceTriageRunResult:
    root = Path(root)
    packets_dir = root / "data" / "source-packets"
    if not packets_dir.exists():
        return SourceTriageRunResult(outcomes=[], agy_calls=0, budget_exhausted=False)

    eligible_packets = []
    for packet_path in sorted(packets_dir.glob("*.json")):
        packet = _load_json(packet_path)
        if _eligible_packet(packet):
            eligible_packets.append(packet_path)

    if not eligible_packets:
        return SourceTriageRunResult(outcomes=[], agy_calls=0, budget_exhausted=False)

    with StateStore(root / "data" / "state.db") as store:
        store.initialize()
        published_source_urls = sorted(store.published_source_urls())
        outcomes: list[TriageOutcome] = []
        agy_calls = 0
        budget_exhausted = False
        processed = 0
        batch_index = 0

        for batch_start in range(0, len(eligible_packets), max(1, batch_size)):
            if max_items is not None and processed >= max_items:
                break
            if budget_limit is not None and agy_calls >= budget_limit:
                budget_exhausted = True
                break

            batch = eligible_packets[batch_start : batch_start + max(1, batch_size)]
            if max_items is not None:
                remaining_items = max_items - processed
                if remaining_items <= 0:
                    break
                batch = batch[:remaining_items]
            if not batch:
                break

            batch_result = _process_batch(
                root,
                batch=batch,
                published_source_urls=published_source_urls,
                runner=runner,
                batch_index=batch_index,
                store=store,
            )
            outcomes.extend(batch_result.outcomes)
            agy_calls += batch_result.agy_calls
            processed += len(batch)
            batch_index += 1

            if budget_limit is not None and agy_calls >= budget_limit:
                budget_exhausted = True
                break

        return SourceTriageRunResult(outcomes=outcomes, agy_calls=agy_calls, budget_exhausted=budget_exhausted)
