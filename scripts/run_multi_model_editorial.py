from __future__ import annotations

import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path

from _bootstrap import add_repo_root_to_path
add_repo_root_to_path()

from uap_news_hub.youtube_editorial import run_youtube_editorial_pipeline
from uap_news_hub.agy import run_agy_worker, AgyRunResult
from uap_news_hub.settings import load_settings


def call_agy_cli(prompt: str) -> str:
    cmd = [
        "agy",
        "--model", "Gemini 3.5 Flash (Low)",
        "--print", prompt,
        "--print-timeout", "10m",
        "--dangerously-skip-permissions"
    ]
    # We pipe empty input via stdin to ensure non-interactive execution
    res = subprocess.run(cmd, input="", capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(f"agy CLI failed (exit {res.returncode}): {res.stderr}")
    return res.stdout.strip()


def call_claude_cli(prompt: str) -> str:
    cmd = [
        "claude",
        "-m", "haiku",
        "-p", prompt
    ]
    res = subprocess.run(cmd, input="", capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(f"claude CLI failed (exit {res.returncode}): {res.stderr}")
    return res.stdout.strip()


def call_codex_cli(prompt: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_output = Path(tmpdir) / "codex_output.txt"
        cmd = [
            "codex",
            "exec",
            "--ephemeral",
            "-m", "gpt-5.4-mini",
            "-o", str(temp_output),
            prompt
        ]
        res = subprocess.run(cmd, input="", capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            raise RuntimeError(f"codex CLI failed (exit {res.returncode}): {res.stderr}")
        if temp_output.exists():
            return temp_output.read_text(encoding="utf-8").strip()
        raise RuntimeError("Codex succeeded but did not write output file")


def multi_model_call(prompt_text: str) -> str:
    if "analyzing a YouTube UFO/UAP transcript" in prompt_text:
        print("  [Routing to agy (Gemini 3.5 Flash Low) for transcript mapping/reduction]")
        return call_agy_cli(prompt_text)
    elif "drafting a UFO/UAP article" in prompt_text:
        print("  [Routing to claude (Claude Haiku) for Skyledger-style editorial writing]")
        return call_claude_cli(prompt_text)
    elif "performing factual review" in prompt_text:
        print("  [Routing to codex (GPT-5.4-Mini) for red-team factual validation]")
        return call_codex_cli(prompt_text)
    else:
        print("  [Routing default to agy (Gemini 3.5 Flash Low)]")
        return call_agy_cli(prompt_text)


def custom_runner(prompt_text: str, save_dir: Path | None = None) -> AgyRunResult:
    # Run the worker with our custom routing function
    # This automatically inherits the JSON verification and retry-to-repair logic from agy module
    return run_agy_worker(prompt_text, call=multi_model_call, save_dir=save_dir)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    settings = load_settings()
    
    print("Starting Multi-Model Consensus Editorial Pipeline...")
    print(f"Daily AGY budget available: {settings.daily_agy_budget}")
    
    result = run_youtube_editorial_pipeline(
        root,
        runner=custom_runner,
        settings=settings
    )
    
    print(f"\nPipeline finished. Processed {len(result.outcomes)} items.")
    print(f"Total AI calls executed: {result.agy_calls}")
    if result.budget_exhausted:
        print("Budget limit reached during run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
