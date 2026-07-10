from __future__ import annotations

import shutil
import importlib.util
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
    has_python_module: Callable[[str], bool] | None = None,
    env: dict[str, str] | None = None,
    free_disk_gb: int | float | None = None,
    run_pip_check: Callable[[], int] | None = None,
    git_push_dry_run: Callable[[], int] | None = None,
) -> EnvironmentCheckResult:
    env = env or {}
    has_python_module = has_python_module or (lambda name: importlib.util.find_spec(name) is not None)
    errors: list[str] = []
    diarization_enabled = str(env.get("UAP_DIARIZATION_ENABLED", "0")).strip().lower() in {"1", "true", "yes", "on"}

    for tool in ("python", "git", "ffmpeg"):
        if which(tool) is None:
            errors.append(f"missing required tool: {tool}")
    if which("yt-dlp") is None and not has_python_module("yt_dlp"):
        errors.append("missing required tool: yt-dlp")
    if which("agy") is None:
        errors.append("missing required tool: agy")
    if diarization_enabled and ("HF_TOKEN" not in env or not env["HF_TOKEN"].strip()):
        errors.append("HF_TOKEN is required when diarization is enabled")
    if free_disk_gb is not None and free_disk_gb < 20:
        errors.append("insufficient free disk space")

    if run_pip_check is not None and run_pip_check() != 0:
        errors.append("python package check failed")
    if git_push_dry_run is not None and git_push_dry_run() != 0:
        errors.append("git push dry-run failed")

    return EnvironmentCheckResult(passed=not errors, errors=errors)
