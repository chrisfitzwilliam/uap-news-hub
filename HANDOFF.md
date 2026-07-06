# Handoff

Current state:

- Core library modules exist for state, validation, ingestion, URLs, locking, site build, and AGY wrapping.
- The site pipeline now has a reusable helper that validates published content, builds the site, and writes run history.
- The hourly and daily scripts call that helper through the existing lock wrapper.
- GitHub Pages publishing now validates content before deploy instead of doing a blind copy.
- Source ingestion now has a real fetch helper with conditional headers and a script entrypoint that uses it.
- Source ingestion now prefers `rss_url` when present, so YouTube registry entries can keep both channel pages and feed URLs.
- Registry entries now persist `etag`, `last_modified`, and `last_checked_at` after ingestion.
- Source ingestion now retries transient fetch failures with backoff.
- Hourly and daily runners now ingest sources before the build/publish step.
- Source ingestion now tracks consecutive failures and auto-deactivates sources that hit the threshold.
- Source ingestion can stop at a packet cap for controlled runs.
- The registry now includes Google News and Reddit live-feed seed entries.
- The registry now also includes an initial live-feed YouTube priority group, and `youtube_channels.json` is wired into ingestion.
- The daily runner now downloads queued YouTube packets and transcribes them before the site build.
- The daily runner now also runs AGY transcript analysis and article drafting before the site build.
- The daily runner now also tracks AGY call totals and stops the editorial pass when the conservative budget is spent.
- The daily runner now also runs AGY factual review and routes non-passing YouTube Intel items to `content/queue/`.
- The daily runner now also batches AGY source triage for new source packets before download/transcribe.
- Validation now writes per-item records under `data/validation/` and checks both queue and published content.
- The next missing slice is static-site expansion and deeper scheduler tuning.

What to do next:

1. Run `pytest -q`.
2. Build out the remaining static-site sections and polish the generated pages.
3. Inspect `site/index.html`, `site/status.html`, and the published YouTube article output after the next build pass.
4. Continue into scheduler behavior after the AGY path is wired.

Machine note:

- Pytest cache access on this host is broken for `.pytest_cache`, so the repo intentionally uses `.pytest-tmp/` and `-p no:cacheprovider` via `pytest.ini`.
