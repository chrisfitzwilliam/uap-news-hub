# UFO / UAP News Hub

Local-first pipeline for collecting UFO/UAP source material, validating it deterministically, and generating a static site.

## Current Status

- Repository-local pytest settings are in `pytest.ini` so tests use `.pytest-tmp/` and avoid the machine-level pytest cache/temp ACL problem.
- `scripts/run_hourly.py` and `scripts/run_daily.py` now call a real site pipeline helper instead of returning dummy success.
- The site pipeline validates published content, builds the static site, and records run history in SQLite.
- GitHub Pages publishing now has a real validated deploy helper instead of a blind copy step.
- Source ingestion now has a real fetch helper and script entrypoint instead of a no-op placeholder.
- Source ingestion now prefers `rss_url` when present so YouTube channel entries can keep both page URLs and feed URLs.
- Registry entries now persist `etag`, `last_modified`, and `last_checked_at` after ingestion.
- Source ingestion now retries transient fetch failures with backoff before giving up.
- Hourly and daily runners now ingest sources before the build/publish step.
- The daily runner now also downloads queued YouTube packets and transcribes downloaded audio before the site build.
- The daily runner now also runs AGY-backed YouTube transcript analysis and article drafting before the site build.
- The daily runner now tracks AGY call totals for the editorial pass and stops once the conservative budget is spent.
- The daily runner now also runs AGY factual review and sends non-passing YouTube Intel items to `content/queue/`.
- Validation now writes per-item records under `data/validation/` and checks queued items as well as published content.
- Source ingestion now increments failure counters and auto-deactivates repeated failures.
- Source ingestion can stop at a packet cap for controlled runs.
- The registry now includes a small live-feed seed set for Google News and Reddit.
- The registry now also includes an initial live-feed YouTube priority set, and `scripts/ingest_sources.py` reads `youtube_channels.json`.
- The latest code changes were paused after YouTube download/transcription, AGY transcript analysis/article drafting, daily-run integration, AGY budgeting, factual review, source triage, and validation hardening, before static-site expansion and deeper scheduler tuning.

## Rules

- No paid APIs.
- Use local tooling first.
- Keep all pipeline timestamps in UTC.
- Keep downloaded media out of git.

## Project layout

- `content/` holds source registry files and published editorial content.
- `data/` holds SQLite state and pipeline artifacts.
- `site/` is generated output for GitHub Pages.
- `templates/` contains versioned site templates.
- `schemas/` contains JSON schemas for AGY outputs and content validation.
- `scripts/` contains pipeline entrypoints.

## Handoff Files

- [CHANGELOG.md](./CHANGELOG.md)
- [TODO.md](./TODO.md)
- [HANDOFF.md](./HANDOFF.md)

## Setup

1. Create a virtual environment if desired.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and fill local secrets.
4. Run `python scripts/check_environment.py`.

## Build

Run `python scripts/build_site.py` to generate the static site from validated content.
