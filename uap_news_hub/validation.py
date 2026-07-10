from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

from .state import StateStore
from .urls import normalize_url
from .utils import utc_now

ALLOWED_CONTENT_TYPES = {
    "latest_briefing",
    "breaking_brief",
    "breaking_watch",
    "youtube_intel",
    "source_digest",
    "claim_tracker",
}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}
ALLOWED_REVIEW_RESULTS = {"pass", "reject", "ignore", "needs_more_sources", "queued"}
PUBLISHED_REVIEW_RESULTS = {"pass"}
QUEUED_REVIEW_RESULTS = ALLOWED_REVIEW_RESULTS - {"pass"}
DEFAULT_OVERCLAIM_PHRASES = [
    "proves aliens",
    "confirmed alien",
    "irrefutable evidence",
]


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


ARTICLE_SCHEMA = {
    "type": "object",
    "required": ["slug", "title", "content_type", "source_urls", "confidence", "body_markdown", "review_result"],
    "properties": {
        "slug": {"type": "string"},
        "title": {"type": "string"},
        "content_type": {"type": "string"},
        "source_urls": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string"},
        "body_markdown": {"type": "string"},
        "review_result": {"type": "string"},
    },
    "additionalProperties": True,
}


def _load_overclaim_phrases(path: Path | None = None) -> list[str]:
    if path and path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("phrases"), list):
            return [str(value).lower() for value in payload["phrases"]]
        if isinstance(payload, list):
            return [str(value).lower() for value in payload]
    return DEFAULT_OVERCLAIM_PHRASES


def _is_https_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _timestamp_to_seconds(value: str) -> float | None:
    parts = str(value).strip().split(":")
    if len(parts) not in {2, 3}:
        return None
    try:
        if len(parts) == 2:
            minutes, seconds = parts
            hours = 0
        else:
            hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return None


def _payload_duration_seconds(payload: dict[str, Any]) -> float | None:
    candidates = [payload.get("video_duration_seconds"), payload.get("duration_seconds")]
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        candidates.extend([metadata.get("video_duration_seconds"), metadata.get("duration_seconds")])
    for candidate in candidates:
        if candidate in (None, ""):
            continue
        try:
            return float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _count_words(text: str) -> int:
    return len([word for word in text.split() if word])


def validate_article_payload(
    payload: dict[str, Any],
    store: StateStore,
    *,
    phrase_config_path: Path | None = None,
    allowed_review_results: set[str] | None = None,
    allow_current_index_record: bool = False,
) -> ValidationResult:
    errors: list[str] = []
    validator = Draft202012Validator(ARTICLE_SCHEMA)
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.path)):
        errors.append(error.message)

    if payload.get("content_type") not in ALLOWED_CONTENT_TYPES:
        errors.append("content_type is not allowed")
    if payload.get("confidence") not in ALLOWED_CONFIDENCE:
        errors.append("confidence is not allowed")
    review_result = payload.get("review_result")
    allowed_review_results = allowed_review_results or PUBLISHED_REVIEW_RESULTS
    if review_result not in allowed_review_results:
        errors.append(f"review_result must be one of: {', '.join(sorted(allowed_review_results))}")

    source_urls = payload.get("source_urls") or []
    if not source_urls:
        errors.append("at least one source_url is required")
    normalized_urls: list[str] = []
    for url in source_urls:
        if not _is_https_url(url):
            errors.append(f"invalid source_url: {url}")
            continue
        normalized_urls.append(normalize_url(url))

    current_slug = str(payload.get("slug", ""))
    current_index_record = store.published_record(current_slug) if allow_current_index_record and current_slug else None

    if current_slug and store.slug_exists(current_slug) and current_index_record is None:
        errors.append("slug already published")
    if payload.get("title"):
        title_owner = store.title_owner(str(payload["title"]))
    else:
        title_owner = None
    if title_owner is not None and title_owner != current_slug:
        errors.append("title already published")
    for url in normalized_urls:
        source_owner = store.source_url_owner(url)
        if source_owner is not None and source_owner != current_slug:
            errors.append(f"source_url already published: {url}")

    body = str(payload.get("body_markdown", ""))
    if not body.strip():
        errors.append("body_markdown must not be empty")

    lower_body = body.lower()
    for phrase in _load_overclaim_phrases(phrase_config_path):
        if phrase in lower_body:
            errors.append(f"overclaiming phrase blocked: {phrase}")

    duration_seconds = _payload_duration_seconds(payload)
    if payload.get("claims"):
        for claim in payload.get("claims", []):
            if not isinstance(claim, dict):
                continue

            quote = str(claim.get("quote", "")).strip()
            if quote and _count_words(quote) > 75:
                errors.append("direct transcript quote exceeds 75 words")

            timestamp_start = claim.get("timestamp_start")
            timestamp_end = claim.get("timestamp_end")
            if timestamp_start and timestamp_end:
                start_seconds = _timestamp_to_seconds(str(timestamp_start))
                end_seconds = _timestamp_to_seconds(str(timestamp_end))
                if start_seconds is None or end_seconds is None:
                    errors.append("claim timestamps must be HH:MM:SS or MM:SS")
                elif end_seconds < start_seconds:
                    errors.append("claim timestamp_end must be after timestamp_start")
                elif duration_seconds is not None and end_seconds > duration_seconds:
                    errors.append("claim timestamp_end exceeds video duration")

            if payload.get("diarization_failed") and claim.get("speaker") not in (None, "UNKNOWN"):
                errors.append("speaker attribution not allowed when diarization_failed")
                break

    return ValidationResult(passed=not errors, errors=errors)


def _validate_content_dir(
    content_dir: Path,
    store: StateStore,
    *,
    subdir_name: str,
    allowed_review_results: set[str],
    phrase_config_path: Path | None = None,
) -> ValidationResult:
    target_dir = content_dir / subdir_name
    if not target_dir.exists():
        return ValidationResult(passed=True)

    errors: list[str] = []
    warnings: list[str] = []
    validation_dir = content_dir.parent / "data" / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(target_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            error_message = f"{subdir_name}/{path.name}: invalid JSON: {exc.msg}"
            errors.append(error_message)
            validation_record = {
                "item_id": path.stem,
                "content_path": str(path.relative_to(content_dir.parent)),
                "validated_at": utc_now(),
                "passed": False,
                "errors": [error_message],
                "warnings": [],
            }
            (validation_dir / f"{path.stem}.json").write_text(
                json.dumps(validation_record, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            continue

        result = validate_article_payload(
            payload,
            store,
            phrase_config_path=phrase_config_path,
            allowed_review_results=allowed_review_results,
            allow_current_index_record=subdir_name == "published",
        )
        warnings.extend(result.warnings)
        validation_record = {
            "item_id": str(payload.get("packet_id") or payload.get("slug") or path.stem),
            "content_path": str(path.relative_to(content_dir.parent)),
            "validated_at": utc_now(),
            "passed": result.passed,
            "errors": result.errors,
            "warnings": result.warnings,
        }
        (validation_dir / f"{validation_record['item_id']}.json").write_text(
            json.dumps(validation_record, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        if not result.passed:
            errors.extend(f"{subdir_name}/{path.name}: {error}" for error in result.errors)

    return ValidationResult(passed=not errors, errors=errors, warnings=warnings)


def validate_published_content(
    content_dir: Path,
    store: StateStore,
    *,
    phrase_config_path: Path | None = None,
) -> ValidationResult:
    return _validate_content_dir(
        content_dir,
        store,
        subdir_name="published",
        allowed_review_results=PUBLISHED_REVIEW_RESULTS,
        phrase_config_path=phrase_config_path,
    )


def validate_queued_content(
    content_dir: Path,
    store: StateStore,
    *,
    phrase_config_path: Path | None = None,
) -> ValidationResult:
    return _validate_content_dir(
        content_dir,
        store,
        subdir_name="queue",
        allowed_review_results=QUEUED_REVIEW_RESULTS,
        phrase_config_path=phrase_config_path,
    )


def validate_all_content(
    content_dir: Path,
    store: StateStore,
    *,
    phrase_config_path: Path | None = None,
) -> ValidationResult:
    published_result = validate_published_content(content_dir, store, phrase_config_path=phrase_config_path)
    queued_result = validate_queued_content(content_dir, store, phrase_config_path=phrase_config_path)
    errors = [*published_result.errors, *queued_result.errors]
    warnings = [*published_result.warnings, *queued_result.warnings]
    return ValidationResult(passed=not errors, errors=errors, warnings=warnings)
