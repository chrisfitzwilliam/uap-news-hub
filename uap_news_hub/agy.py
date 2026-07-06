from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any
import subprocess
import os

from .utils import ensure_parent


@dataclass
class AgyRunResult:
    raw_text: str
    parsed: Any
    call_count: int
    save_dir: Path | None = None


def extract_json_document(text: str) -> Any:
    cleaned = text.strip()
    code_fence = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if code_fence:
        cleaned = code_fence.group(1).strip()
    start_candidates = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
    if start_candidates:
        cleaned = cleaned[min(start_candidates):].strip()
    return json.loads(cleaned)


def call_agy(prompt_text: str, *, timeout_seconds: int = 720) -> str:
    command = [
        "agy",
        "--print",
        "--add-dir",
        ".",
        "--print-timeout",
        "10m",
        prompt_text,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=os.environ.copy(),
    )
    return completed.stdout.strip()


def run_agy_worker(
    prompt_text: str,
    *,
    call: Callable[[str], str] | None = None,
    save_dir: Path | None = None,
) -> AgyRunResult:
    call = call or call_agy
    raw = call(prompt_text)
    call_count = 1
    try:
        parsed = extract_json_document(raw)
    except Exception:
        repair_prompt = f"Repair the following output so it is valid JSON only:\n{raw}"
        raw = call(repair_prompt)
        call_count += 1
        parsed = extract_json_document(raw)

    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / "raw.txt").write_text(raw, encoding="utf-8")
        (save_dir / "parsed.json").write_text(json.dumps(parsed, indent=2, sort_keys=True), encoding="utf-8")
    return AgyRunResult(raw_text=raw, parsed=parsed, call_count=call_count, save_dir=save_dir)
