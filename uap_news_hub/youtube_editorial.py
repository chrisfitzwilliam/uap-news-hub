from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .agy import AgyRunResult, run_agy_worker
from .state import StateStore
from .urls import normalize_url
from .utils import utc_now, write_json


YOUTUBE_ANALYSIS_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "youtube_analysis.schema.json"
ARTICLE_DRAFT_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "article_draft.schema.json"
FACTUAL_REVIEW_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "factual_review.schema.json"
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
MIN_CALLS_PER_ITEM = 3


@dataclass
class EditorialOutcome:
    video_id: str
    analysis: dict[str, Any]
    draft: dict[str, Any]
    review: dict[str, Any]
    article_path: Path | None
    analysis_run_dir: Path
    draft_run_dir: Path
    review_run_dir: Path
    call_count: int


@dataclass
class EditorialRunResult:
    outcomes: list[EditorialOutcome]
    agy_calls: int
    budget_exhausted: bool


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_prompt(name: str) -> str:
    prompt_path = PROMPTS_DIR / name
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return ""


def _render_prompt(prompt_name: str, *, packet: dict[str, Any], metadata: dict[str, Any], transcript: dict[str, Any], extra: dict[str, Any]) -> str:
    parts = [_load_prompt(prompt_name)]
    context = {
        "packet": packet,
        "metadata": metadata,
        "transcript": transcript,
        "extra": extra,
    }
    parts.append("INPUT_JSON:")
    parts.append(json.dumps(context, indent=2, sort_keys=True))
    parts.append("Return JSON only, no markdown fences, no preamble.")
    return "\n\n".join(part for part in parts if part)


def _validate_payload(payload: dict[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        raise ValueError("; ".join(error.message for error in errors))


def _article_payload_from_draft(draft: dict[str, Any], *, source_url: str) -> dict[str, Any]:
    source_urls = [source_url]
    for source in draft.get("sources", []):
        if isinstance(source, dict):
            url = str(source.get("url", "")).strip()
            if url and url not in source_urls:
                source_urls.append(url)
    article = {
        "slug": draft["slug"],
        "title": draft["title"],
        "dek": draft["dek"],
        "content_type": draft["content_type"],
        "confidence": draft["confidence"],
        "source_urls": source_urls,
        "body_markdown": draft["article_markdown"],
    }
    for key in ("claim_labels", "related_claims"):
        if key in draft:
            article[key] = draft[key]
    return article


def _run_item(
    root: Path,
    *,
    transcript_path: Path,
    metadata_path: Path,
    runner: Callable[..., AgyRunResult],
) -> EditorialOutcome:
    transcript = _load_json(transcript_path)
    metadata = _load_json(metadata_path)
    packet = {
        "packet_id": metadata.get("packet_id"),
        "source_url": metadata.get("source_url"),
        "title": metadata.get("title"),
        "video_id": metadata.get("video_id"),
    }
    video_id = str(metadata.get("video_id") or transcript_path.stem)
    source_url = str(metadata.get("source_url") or transcript.get("source_url") or "")
    normalized_source_url = normalize_url(source_url) if source_url else source_url

    analysis_run_dir = root / "data" / "agy-runs" / "latest" / "youtube" / video_id / "analysis"
    draft_run_dir = root / "data" / "agy-runs" / "latest" / "youtube" / video_id / "draft"
    review_run_dir = root / "data" / "agy-runs" / "latest" / "youtube" / video_id / "review"

    analysis_prompt = _render_prompt(
        "youtube_analysis.md",
        packet=packet,
        metadata=metadata,
        transcript=transcript,
        extra={"source_url": source_url},
    )
    analysis_result = runner(analysis_prompt, save_dir=analysis_run_dir)
    analysis = analysis_result.parsed if isinstance(analysis_result.parsed, dict) else {}
    _validate_payload(analysis, YOUTUBE_ANALYSIS_SCHEMA)

    draft_prompt = _render_prompt(
        "article_draft.md",
        packet=packet,
        metadata=metadata,
        transcript=transcript,
        extra={"analysis": analysis, "source_url": source_url},
    )
    draft_result = runner(draft_prompt, save_dir=draft_run_dir)
    draft = draft_result.parsed if isinstance(draft_result.parsed, dict) else {}
    _validate_payload(draft, ARTICLE_DRAFT_SCHEMA)

    review_prompt = _render_prompt(
        "factual_review.md",
        packet=packet,
        metadata=metadata,
        transcript=transcript,
        extra={"analysis": analysis, "draft": draft, "source_url": source_url},
    )
    review_result = runner(review_prompt, save_dir=review_run_dir)
    review = review_result.parsed if isinstance(review_result.parsed, dict) else {}
    _validate_payload(review, FACTUAL_REVIEW_SCHEMA)

    article = _article_payload_from_draft(draft, source_url=normalized_source_url or source_url)
    review_result_value = str(review.get("review_result", "reject"))
    article["review_result"] = review_result_value
    article["reviewed_at"] = utc_now()
    if review_result_value == "pass" and draft.get("should_publish", False):
        article["published_at"] = article["reviewed_at"]
        destination_dir = root / "content" / "published"
    else:
        article["queued_at"] = article["reviewed_at"]
        destination_dir = root / "content" / "queue"

    article_path: Path | None = None
    destination_dir.mkdir(parents=True, exist_ok=True)
    article_path = destination_dir / f"{article['slug']}.json"
    write_json(article_path, article)

    with StateStore(root / "data" / "state.db") as state:
        state.initialize()
        if review_result_value == "pass" and draft.get("should_publish", False):
            state.record_published_index(
                slug=article["slug"],
                title=article["title"],
                content_type=article["content_type"],
                source_urls=article["source_urls"],
                published_at=article["published_at"],
            )

    return EditorialOutcome(
        video_id=video_id,
        analysis=analysis,
        draft=draft,
        review=review,
        article_path=article_path,
        analysis_run_dir=analysis_run_dir,
        draft_run_dir=draft_run_dir,
        review_run_dir=review_run_dir,
        call_count=analysis_result.call_count + draft_result.call_count + review_result.call_count,
    )


def run_youtube_editorial_pipeline(
    root: Path,
    *,
    runner: Callable[..., AgyRunResult] = run_agy_worker,
    max_items: int | None = None,
    budget_limit: int | None = None,
) -> EditorialRunResult:
    root = Path(root)
    transcript_root = root / "data" / "transcripts"
    download_root = root / "data" / "downloads"
    if not transcript_root.exists():
        return EditorialRunResult(outcomes=[], agy_calls=0, budget_exhausted=False)

    outcomes: list[EditorialOutcome] = []
    processed = 0
    agy_calls = 0
    budget_exhausted = False
    for transcript_path in sorted(transcript_root.glob("*.json")):
        if max_items is not None and processed >= max_items:
            break
        if budget_limit is not None and (budget_limit - agy_calls) < MIN_CALLS_PER_ITEM:
            budget_exhausted = True
            break
        video_id = transcript_path.stem
        metadata_path = download_root / video_id / "metadata.json"
        if not metadata_path.exists():
            continue
        outcome = _run_item(root, transcript_path=transcript_path, metadata_path=metadata_path, runner=runner)
        outcomes.append(outcome)
        agy_calls += outcome.call_count
        processed += 1
    if budget_limit is not None and agy_calls >= budget_limit:
        budget_exhausted = True
    return EditorialRunResult(outcomes=outcomes, agy_calls=agy_calls, budget_exhausted=budget_exhausted)
