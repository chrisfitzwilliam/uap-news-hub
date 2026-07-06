# Changelog

## Unreleased

- Added `pytest.ini` so pytest uses a repo-local temp dir and skips the broken cache provider on this machine.
- Added `run_site_pipeline` to validate published content, build the site, and record run history in SQLite.
- Wired `scripts/run_hourly.py` and `scripts/run_daily.py` to the site pipeline helper.
- Improved site building with a proper Jinja loader fallback and safer status timestamp handling.
- Added `validate_published_content` to validate the published content directory as a batch.
- Added a real publish helper and wired `scripts/publish_github_pages.py` to it.
- Added publish tests for validated deploy success and fail-closed malformed content.
- Added a real ingestion fetch helper, conditional header support, and a script entrypoint that uses it.
- Added ingestion tests for conditional GET headers, packet writing, and script orchestration.
- Added registry persistence for `etag`, `last_modified`, and `last_checked_at` after ingestion.
- Added retry/backoff handling for transient source-fetch failures.
- Added ingestion tests for retry behavior.
- Wired hourly and daily runners to ingest before the site pipeline runs.
- Added scheduler orchestration coverage for hourly ingestion before build.
- Added fetch failure bookkeeping with consecutive-failure increments and auto-deactivation.
- Added ingestion tests for failure bookkeeping and deactivation.
- Added packet-cap handling to ingestion for controlled runs.
- Added ingestion tests for packet-cap behavior.
- Seeded the registry with Google News and Reddit live-feed sources.
- Added `rss_url` support so registry entries can keep both human page URLs and feed URLs.
- Seeded the registry with an initial YouTube priority set and matching source-change entries.
- Taught ingestion to read `youtube_channels.json` and normalize its packets to `source_type = youtube`.
- Added a real YouTube download worker with packet state updates, audio normalization, and failure tracking.
- Added a real transcript worker that normalizes transcript payloads and writes JSON/text outputs.
- Added AGY-backed YouTube transcript analysis and article drafting with versioned prompt files.
- Added budget-aware AGY editorial accounting so daily runs stop after the configured call cap and record totals.
- Added AGY factual review and queue/publish routing for YouTube Intel items.
- Added batch AGY source triage for source packets with packet-status updates and daily-run integration.
- Added validation hardening for queue and published content, including claim quote/timestamp checks and per-item validation records.
- Wired the daily runner to ingest, download YouTube media, transcribe audio, draft YouTube Intel articles, review them, account for AGY calls, and then build the site.
- Added regression tests using the live YouTube URL `https://www.youtube.com/watch?v=A2-y_HasHEw`.
