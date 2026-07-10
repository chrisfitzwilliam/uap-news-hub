# UFO / UAP News Hub

An evidence-first, local-first static newsroom. Local Windows jobs collect and assess source material with AGY and local transcription; only validated editorial JSON is committed to `main`. GitHub Actions tests, builds, and deploys the generated site to GitHub Pages.

## Redesign completed (2026-07-10)

The visual redesign has been successfully implemented and deployed. The direction is **Night Sky Observatory**: near-black surfaces, lunar-white typography, restrained electric-cyan scientific accents, spacious editorial rhythm, and no cartoon-alien styling. The audience bridges curious readers and serious UAP researchers, leaning slightly toward the research audience. The homepage hierarchy is **Briefing + Evidence Grid**: one accessible lead briefing followed immediately by evidence-library, claim-tracker, YouTube-intel, source, and methodology entry points.

The publication name is **Skyledger** and the custom domain is deployed to `skyledger.space`. The domain is managed via Cloudflare DNS pointing to GitHub Pages.

## Editorial safety

- The site reports source-backed claims, not confirmations.
- `content/published/` is public, versioned editorial record. `content/queue/` and `content/rejected/` are auditable non-public records.
- `data/state.db`, transcripts, media, AGY artifacts, logs, and generated `site/` are local runtime artifacts and are not versioned.
- A malformed AGY response, timeout, schema failure, review failure, exhausted budget, lock, or dirty unrelated Git change fails closed.
- `UAP_WHISPER_MODEL=small` is the final-candidate default. `tiny` transcripts are exploratory only and must be re-run before publication.

## Modes and emergency control

Set these in a local `.env` (or persistent environment), then start in `supervised` for seven reviewed daily runs.

```powershell
UAPNEWSHUB_PIPELINE_MODE=supervised
UAPNEWSHUB_ENABLE_PUBLISH=0
UAPNEWSHUB_EMERGENCY_STOP=0
UAPNEWSHUB_SITE_URL=https://chrisfitzwilliam.github.io/uap-news-hub
```

- `dry-run`: ingests and evaluates but never writes public or queue content and never commits.
- `supervised`: creates auditable candidates in `content/queue/`; publishing remains disabled.
- `autonomous`: may publish only when `UAPNEWSHUB_ENABLE_PUBLISH=1` and `UAPNEWSHUB_EMERGENCY_STOP=0`.

The persistent `UAPNEWSHUB_EMERGENCY_STOP=1` prevents all automatic publication while retaining diagnostics and status output.

## Local commands

```powershell
pip install -r requirements.txt
python scripts/check_environment.py
pytest -q
python scripts/validate_outputs.py
python scripts/build_site.py
python scripts/run_hourly.py
python scripts/run_daily.py
```

Install idempotent scheduled jobs after the supervised run is accepted:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_task_scheduler.ps1 -Action install
powershell -ExecutionPolicy Bypass -File scripts/install_task_scheduler.ps1 -Action status
powershell -ExecutionPolicy Bypass -File scripts/install_task_scheduler.ps1 -Action uninstall
```

Jobs use Task Scheduler's `IgnoreNew` overlap policy and the Python stale-lock recovery guard. Structured event logs are written to `data/logs/`; the status page flags stale successful runs.

## GitHub Pages launch

The live repository is [chrisfitzwilliam/uap-news-hub](https://github.com/chrisfitzwilliam/uap-news-hub) and the current Pages site is [https://chrisfitzwilliam.github.io/uap-news-hub/](https://chrisfitzwilliam.github.io/uap-news-hub/). It deploys from `main` through GitHub Actions with HTTPS enabled.

1. Keep the repository Actions variable `UAPNEWSHUB_SITE_URL` set to the Pages or final custom-domain URL.
2. Add a protected `github-pages` environment if desired. The workflow in `.github/workflows/pages.yml` runs validation/tests, builds with `UAPNEWSHUB_SITE_URL`, uploads `site/`, then deploys it.
3. For a custom domain, configure it in GitHub before DNS, verify the domain, add GitHub's required records, and enable HTTPS.
4. Keep the pipeline in `supervised` for seven consecutive reviewed daily runs. Only then set `UAPNEWSHUB_PIPELINE_MODE=autonomous` and `UAPNEWSHUB_ENABLE_PUBLISH=1`.

## Current baseline

The public site starts with seven source-linked, evidence-first explainers: NASA’s evidence standard, the FY2024 ODNI report, AARO reporting trends and FAQ guidance, AARO’s historical-record review and imagery archive, and the introduced UAP Transparency Act. The single-source Burlison transcript item remains in `content/queue/` until it is re-transcribed with `small` and independently corroborated.

The local publisher commits only changes beneath `content/published/`, `content/queue/`, or `content/rejected/`, then pushes `main`. Any other dirty path blocks publication.
