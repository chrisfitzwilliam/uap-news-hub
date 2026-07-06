from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class EnvironmentCheckResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_environment(
    *,
    which: Callable[[str], str | None] = shutil.which,
    env: dict[str, str] | None = None,
    free_disk_gb: int | float | None = None,
    run_pip_check: Callable[[], int] | None = None,
    git_push_dry_run: Callable[[], int] | None = None,
) -> EnvironmentCheckResult:
    env = env or {}
    errors: list[str] = []

    for tool in ("python", "git", "ffmpeg", "yt-dlp"):
        if which(tool) is None:
            errors.append(f"missing required tool: {tool}")
    if which("agy") is None:
        errors.append("missing required tool: agy")
    if "HF_TOKEN" not in env or not env["HF_TOKEN"].strip():
        errors.append("HF_TOKEN is required when diarization is enabled")
    if free_disk_gb is not None and free_disk_gb < 20:
        errors.append("insufficient free disk space")

    if run_pip_check is not None and run_pip_check() != 0:
        errors.append("python package check failed")
    if git_push_dry_run is not None and git_push_dry_run() != 0:
        errors.append("git push dry-run failed")

    return EnvironmentCheckResult(passed=not errors, errors=errors)

