# Handoff

## Completed launch implementation

- Final public content uses `uap-evidence-standards`; the prior one-source `tiny`-transcript Burlison piece is a queued supervised candidate, not a public article.
- SQLite is disposable local state. `StateStore.initialize()` rebuilds its publication index from versioned `content/published/` files.
- Long transcripts are split on segment boundaries, analyzed per chunk, and aggregated source-groundedly before drafting/review.
- Pipeline configuration is centralized in `uap_news_hub/settings.py`; `.env.example` documents caps, budgets, model, mode, URL, enablement, and emergency stop.
- `dry-run`, `supervised`, and `autonomous` publication gates are enforced in the editorial worker. Dry runs do not write editorial files.
- Structured JSONL events go to `data/logs/`; stale locks/runs, failures, budget exhaustion, and publishing are recorded.
- The publisher is source-only: it validates, rejects unexpected dirty paths, commits allowlisted editorial JSON atomically to `main`, and pushes. It does not copy `_gh_pages`.
- `.github/workflows/pages.yml` uses Python 3.12 and artifact-based GitHub Pages deployment.
- Build output includes About, standards, corrections, contact, RSS discovery, favicon, social/canonical metadata, `robots.txt`, sitemap, and a stale-run warning.

## Next operator actions

1. Run the suite and local build from a clean PowerShell session.
2. Configure a real `.env`, Git remote/auth, and the GitHub Pages Actions source.
3. Conduct the seven-day supervised proving run before autonomous publishing.

## Host notes

- The repository uses `.pytest-tmp/` and disables pytest cache due to the host ACL issue.
- Local `faster-whisper` can be blocked by Windows application control; `openai-whisper` remains the fallback.
