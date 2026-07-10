from __future__ import annotations

import os
from dataclasses import dataclass


VALID_PIPELINE_MODES = {"dry-run", "supervised", "autonomous"}


def _int(env: dict[str, str], key: str, default: int) -> int:
    try:
        value = int(env.get(key, str(default)))
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{key} must not be negative")
    return value


def _bool(env: dict[str, str], key: str, default: bool = False) -> bool:
    return env.get(key, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PipelineSettings:
    mode: str
    publishing_enabled: bool
    emergency_stop: bool
    site_url: str
    hourly_packet_cap: int
    daily_packet_cap: int
    daily_download_cap: int
    daily_transcription_cap: int
    hourly_agy_budget: int
    daily_agy_budget: int
    whisper_model: str
    transcript_chunk_chars: int

    @property
    def may_publish(self) -> bool:
        return self.mode == "autonomous" and self.publishing_enabled and not self.emergency_stop


def load_settings(env: dict[str, str] | None = None) -> PipelineSettings:
    env = dict(os.environ if env is None else env)
    mode = env.get("UAPNEWSHUB_PIPELINE_MODE", "supervised").strip().lower()
    if mode not in VALID_PIPELINE_MODES:
        raise ValueError("UAPNEWSHUB_PIPELINE_MODE must be dry-run, supervised, or autonomous")
    return PipelineSettings(
        mode=mode,
        publishing_enabled=_bool(env, "UAPNEWSHUB_ENABLE_PUBLISH"),
        emergency_stop=_bool(env, "UAPNEWSHUB_EMERGENCY_STOP"),
        site_url=env.get("UAPNEWSHUB_SITE_URL", "").strip(),
        hourly_packet_cap=_int(env, "UAPNEWSHUB_HOURLY_INGEST_CAP", 20),
        daily_packet_cap=_int(env, "UAPNEWSHUB_DAILY_INGEST_CAP", 80),
        daily_download_cap=_int(env, "UAPNEWSHUB_DAILY_DOWNLOAD_CAP", 4),
        daily_transcription_cap=_int(env, "UAPNEWSHUB_DAILY_TRANSCRIPTION_CAP", 2),
        hourly_agy_budget=_int(env, "UAPNEWSHUB_AGY_HOURLY_BUDGET", 3),
        daily_agy_budget=_int(env, "UAPNEWSHUB_AGY_DAILY_BUDGET", 25),
        whisper_model=env.get("UAP_WHISPER_MODEL", "small").strip() or "small",
        transcript_chunk_chars=_int(env, "UAPNEWSHUB_TRANSCRIPT_CHUNK_CHARS", 14000),
    )
