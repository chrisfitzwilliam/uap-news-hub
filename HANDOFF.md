# Handoff

## Completed Redesign and Domain Setup

The visual redesign of the public site is complete. 

Approved and implemented decisions:
- Publication Name: **Skyledger**
- Custom Domain: **skyledger.space** (managed via Cloudflare DNS and deployed via GitHub Pages).
- Visual direction: **Night Sky Observatory** — near-black, lunar white, restrained electric cyan, scientific plotting/details, spacious premium typography, and no cartoon-alien or generic purple AI styling.
- Audience: balanced between curious mainstream readers and serious UAP researchers, leaning slightly toward serious research.
- Homepage hierarchy: **Briefing + Evidence Grid** — an accessible lead briefing first, with evidence library, claim tracker, YouTube intel, sources, and methodology immediately visible.
- Existing evidence-first, local-first, deterministic, fail-closed publishing architecture remains unchanged by the visual redesign.

The domain and styling are active and live at `https://skyledger.space`.

## Completed launch implementation

- Public source and deployment are live: [repository](https://github.com/chrisfitzwilliam/uap-news-hub), [Pages site](https://chrisfitzwilliam.github.io/uap-news-hub/), and Actions-based Pages with HTTPS enabled.
- The launch baseline now contains seven public, primary-source-linked articles. They cover NASA’s evidence standard, the FY2024 ODNI report, AARO trends/FAQ/history/imagery, and the introduced UAP Transparency Act.
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

1. Configure a real local `.env` for the scheduler, including a production contact endpoint if one is available.
2. Run a seeded `dry-run`, then complete seven consecutive supervised daily runs; inspect all queued candidates and pipeline alerts.
3. Re-transcribe and independently corroborate the queued Burlison candidate before any promotion to `content/published/`.
4. Install the Task Scheduler jobs with the unattended Windows account credential only after the supervised process is accepted.
5. Add a custom domain later if desired; Pages currently serves successfully from the GitHub URL.

## Host notes

- The repository uses `.pytest-tmp/` and disables pytest cache due to the host ACL issue.
- Local `faster-whisper` can be blocked by Windows application control; `openai-whisper` remains the fallback.
