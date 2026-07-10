# UFO / UAP News Hub

An evidence-first, local-first static newsroom. Local Windows jobs collect and assess source material with AGY and local transcription; only validated editorial JSON is committed to `main`. GitHub Actions tests, builds, and deploys the generated site to GitHub Pages.

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
UAPNEWSHUB_SITE_URL=https://OWNER.github.io/REPOSITORY
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

1. Create a public repository, push this branch as `main`, and select **GitHub Actions** as the Pages source.
2. Add a protected `github-pages` environment if desired. The workflow in `.github/workflows/pages.yml` runs validation/tests, builds with `UAPNEWSHUB_SITE_URL`, uploads `site/`, then deploys it.
3. Set the repository Actions variable `UAPNEWSHUB_SITE_URL` to the final Pages or custom-domain URL.
4. For a custom domain, configure it in GitHub before DNS, verify the domain, add GitHub's required records, and enable HTTPS.
5. Keep the pipeline in `supervised` for seven consecutive reviewed daily runs. Only then set `UAPNEWSHUB_PIPELINE_MODE=autonomous` and `UAPNEWSHUB_ENABLE_PUBLISH=1`.

The local publisher commits only changes beneath `content/published/`, `content/queue/`, or `content/rejected/`, then pushes `main`. Any other dirty path blocks publication.
