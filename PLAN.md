# AGY-Driven UFO/UAP News Hub — Implementation Plan (v2)

> **Launch implementation update (2026-07-10):** The historic plan below originally described a `gh-pages` worktree/force-push flow. The implemented launch design supersedes that choice: generated `site/` output remains local and ignored; only validated, allowlisted editorial JSON is committed to `main`; `.github/workflows/pages.yml` tests, builds, uploads, and deploys the Pages artifact. Runtime SQLite, media, transcripts, AGY artifacts, and logs are local-only. See `README.md` and `HANDOFF.md` for the active operating procedure.

## Current State (Post-Redesign)

- The **Night Sky Observatory** redesign was implemented on 2026-07-10. This included new global navigation, extraction of hardcoded CSS into `theme.css`, and a new homepage layout with a **Briefing + Evidence Grid**.
- The publication name is finalized as **Skyledger**.
- The custom domain `skyledger.space` is fully configured using Cloudflare DNS and GitHub Pages.
- Live launch state (2026-07-10): `main` is published at `https://github.com/chrisfitzwilliam/uap-news-hub`; Actions deploys to `https://skyledger.space` with HTTPS enforced.
- Current public baseline: seven evidence-first, primary-source-linked articles. The Burlison YouTube item is intentionally held in `content/queue/` pending a `small` transcript and independent corroboration.

- Latest completed slice: Full site redesign implementation, domain configuration via Cloudflare API, repo-local pytest config, a real site-pipeline helper, a validated publish helper with dirty-source fail-closed guard, a real ingestion fetch helper, registry metadata persistence for conditional GETs, retry/backoff for transient fetch failures, scheduler orchestration that ingests before build/publish, failure bookkeeping with auto-deactivation, packet-cap handling, live-feed registry seed entries including the 10-channel YouTube priority group, a real YouTube download worker, a transcript writer, `openai-whisper` fallback transcription, AGY large-prompt file handoff, AGY-backed YouTube transcript analysis/article drafting, factual review, batch source triage, queue/publish routing, validation records, budget-aware AGY call accounting for daily runs, expanded static-site generation with section indexes, article surfaces, RSS, sitemap, status counts, a dedicated YouTube channel dashboard, a baseline reviewable rough draft article, and a first transcript-derived YouTube Intel rough draft.
- Host-specific note: `.pytest_cache` is ACL-locked on this machine, so the repo uses `.pytest-tmp/` and disables the cache provider in `pytest.ini`.
- Host-specific note: `faster-whisper` imports are blocked by local Windows application-control policy through PyAV native extension loading, so the working local fallback is `openai-whisper`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous UFO/UAP news website that searches for current news, Reddit posts, YouTube uploads, and other source material, then uses AGY CLI plus local transcription/diarization to generate sourced, evidence-first reporting.

**Architecture:** Static-site generator backed by local Markdown/JSON content files and a SQLite state database. Local scheduled scripts collect sources, download/transcribe YouTube videos, ask AGY to triage/analyze/draft/review content, validate outputs deterministically, rebuild the site, and auto-push to GitHub Pages only when validation passes.

**Tech Stack:** Windows PowerShell, Python 3.12, AGY CLI (`agy`), `yt-dlp`, `ffmpeg`, `faster-whisper` with `openai-whisper` fallback, optional WhisperX or `pyannote.audio`, SQLite (pipeline state), Jinja2 (templating), `jsonschema` (validation), Markdown/JSON content files, static HTML/CSS/JS, GitHub Pages, Windows Task Scheduler.

**v2 changes:** Added Phase 0 prerequisites, SQLite state store, YouTube download hardening (bot detection/rate caps), AGY budget guard, stale-lock handling, media retention policy, GitHub Pages branch strategy to prevent repo bloat, failure alerting, Claim Tracker data model, feed politeness rules, UTC timestamp standard, and a Known Risks section.

---

## 0. Prerequisites And One-Time Decisions

Complete these before Phase 1. Each is a blocker later if skipped.

- [ ] **Hugging Face account + token.** `pyannote.audio` diarization models are gated. You must accept the model license on huggingface.co (e.g. `pyannote/speaker-diarization-3.1` and `pyannote/segmentation-3.0`) and generate a read token. Store it in a local `.env` file (git-ignored) or Windows Credential Manager — never in the repo.
- [ ] **GPU check.** Run `nvidia-smi`. faster-whisper on GPU transcribes ~1hr of audio in a few minutes; CPU-only can take 30–60+ minutes per hour of audio with `medium`. Decide the model size now: GPU → `medium` or `large-v3`; CPU-only → `small` or `base` and accept lower accuracy, or cap daily transcription volume.
- [ ] **GitHub Pages publish strategy.** Decide: (a) serve from `docs/` on `main`, or (b) force-push a single-commit `gh-pages` branch. Option (b) is strongly recommended — committing generated HTML to `main` on every hourly run will bloat the repo into the GB range within months. Keep source/content on `main`; deploy generated `site/` to `gh-pages` with history squashed.
- [ ] **Git auth for unattended pushes.** Configure an SSH key or Git Credential Manager so scheduled pushes never prompt interactively. Test with a manual push first.
- [ ] **YouTube cookies decision.** Scheduled `yt-dlp` runs from a residential IP will eventually hit "Sign in to confirm you're not a bot" errors. Decide up front: export browser cookies for yt-dlp (`--cookies-from-browser`) using a throwaway Google account, or accept intermittent download failures and design retries around them. Never use your primary Google account.
- [ ] **Timezone standard.** All pipeline timestamps are UTC ISO-8601 (`2026-07-06T18:00:00Z`). Local time appears only in rendered page display strings. Mixed timezones in state files cause dedup and ordering bugs.

## 1. Non-Negotiable Constraints

- Do not use `gcloud`.
- Do not use Vertex AI.
- Do not use Google Cloud APIs.
- Do not use OpenAI API.
- Do not use Gemini API.
- Do not use any paid API path unless the user explicitly changes this rule later.
- Use AGY CLI as the primary AI system for searching, article generation, review, site-content generation, and source-list maintenance.
- Use local tooling for YouTube downloads, audio normalization, transcription, and speaker diarization.
- Fail closed: if a stage fails, malformed output is produced, citations are missing, or git publishing fails, do not publish partial content.
- Preserve auditability: every published story must trace back to source packets, prompts, AGY outputs, validation results, and generated article files.
- All internal timestamps are UTC. No secrets, tokens, or cookie files ever enter git.
- Respect an AGY invocation budget per run (see Section 9). If the budget is exhausted, queue remaining work for the next run — do not skip validation to save calls.

## 2. Product Summary

The website should feel like a professional UFO/UAP intelligence desk rather than a rumor blog. It should cover the latest updates, news reports, YouTube analysis, Reddit signals, source digests, and developing claim threads.

The editorial stance is evidence-first neutral:

- Report what happened.
- Identify who made each claim.
- Link to the source.
- Separate confirmed facts from reported claims and AGY analysis.
- Avoid unsupported conclusions.
- Avoid sensational wording when evidence is weak.
- Use confidence labels instead of pretending uncertain material is confirmed.

The site is fully autonomous after setup, but only inside strict validation rules.

## 3. Site Sections

### Latest Briefings

Longer, sourced articles for items that pass the strongest validation checks. These should read like professional news analysis: summary, source history, what is known, what is claimed, evidence, open questions, and links.

### Breaking Watch

Shorter developing-news cards produced by hourly checks. These should be conservative. A breaking item may publish only if it has source URLs and clear claim labels.

### YouTube Intel

Analysis of monitored UFO/UAP YouTube channels. Each entry should include video metadata, publication time, channel, transcript-derived summary, key claims, speaker-labeled excerpts, and source links.

### YouTube Channel Analysis

A dedicated `/youtube/index.html` dashboard for the 10 monitored channels. It should show why each channel is watched, the latest locally staged episodes, download status, transcript status, and enough context for a reviewer to decide which channel or episode deserves the next article draft.

### Source Digest

Daily digest of notable activity across news feeds, Reddit/public forums, YouTube channels, and AGY-discovered source changes.

### Claim Tracker

A structured tracker for recurring UFO/UAP claims, grouped by event or topic. Each claim records source, date, confidence, evidence type, article links, and whether new evidence changed the assessment. See Section 14 for the data model.

### Status Page (internal-facing but public)

A simple `/status.html` generated on every build: last successful hourly run, last successful daily run, last publish time, and counts of queued/rejected items. This is the cheapest possible monitoring — if the timestamps go stale, the pipeline is broken.

## 4. Visual Direction

Use an "intelligence briefing" theme:

- Dark professional newsroom base.
- Dossier-style article cards.
- Evidence and source panels.
- Confidence badges.
- Timeline blocks.
- Transcript quote blocks with speaker labels.
- Subtle grid/radar/starfield background details.
- Crisp typography and strong hierarchy.
- Avoid cartoon alien styling.
- Avoid generic purple-on-white AI-app styling.

Visual language should communicate seriousness, source discipline, and investigation. Include basic SEO/meta hygiene in templates: title tags, meta descriptions, Open Graph tags, canonical URLs, and a favicon.

## 5. Recommended Repository Layout

Create the project as a static site plus local automation pipeline:

```text
.
|-- PLAN.md
|-- README.md
|-- .env.example              # documents required env vars; real .env is git-ignored
|-- .gitignore
|-- requirements.txt
|-- site/                     # generated output; deployed to gh-pages, git-ignored on main
|   |-- index.html
|   |-- status.html
|   |-- .nojekyll
|   |-- assets/
|   |   |-- css/theme.css
|   |   |-- js/app.js
|   |   `-- img/
|   |-- articles/
|   |-- youtube/
|   |-- briefings/
|   |-- youtube-intel/
|   |-- source-digest/
|   `-- claim-tracker/
|-- templates/                # Jinja2 templates (versioned)
|   |-- base.html
|   |-- article.html
|   |-- index.html
|   |-- sections/
|   |-- youtube/
|   `-- status.html
|-- content/
|   |-- published/
|   |-- queue/
|   |-- rejected/
|   |-- sources/
|   |-- claims/               # claim tracker records (JSON)
|   `-- registry/
|-- data/
|   |-- state.db              # SQLite: processed items, publish index, run history
|   |-- source-packets/
|   |-- transcripts/
|   |-- downloads/            # git-ignored; subject to retention policy
|   |-- agy-runs/
|   |-- validation/
|   `-- logs/
|-- schemas/                  # jsonschema files for every AGY output stage
|   |-- triage.schema.json
|   |-- youtube_analysis.schema.json
|   |-- article_draft.schema.json
|   |-- factual_review.schema.json
|   `-- claim.schema.json
|-- prompts/
|   |-- source_triage.md
|   |-- youtube_analysis.md
|   |-- article_draft.md
|   |-- factual_review.md
|   `-- source_registry_maintenance.md
|-- scripts/
|   |-- check_environment.ps1
|   |-- run_hourly.ps1
|   |-- run_daily.ps1
|   |-- ingest_sources.py
|   |-- download_youtube.py
|   |-- transcribe_diarize.py
|   |-- run_agy_worker.py
|   |-- validate_outputs.py
|   |-- update_claims.py
|   |-- build_site.py
|   |-- cleanup_media.py
|   |-- notify_failure.ps1
|   |-- publish_github_pages.ps1
|   `-- install_task_scheduler.ps1
`-- tests/
    |-- fixtures/
    |-- test_ingest_sources.py
    |-- test_validate_outputs.py
    |-- test_build_site.py
    |-- test_state_db.py
    `-- test_transcript_format.py
```

Notes:

- `site/` is generated and deployed to the `gh-pages` branch; it should be in `.gitignore` on `main` so generated HTML never bloats source history.
- `templates/` and `schemas/` are versioned so rendering and validation changes show up in diffs.
- `data/state.db` is the single source of truth for "have we seen/processed/published this?" — scanning folders for dedup does not scale and breaks when files move.
- `content/` stores editorial content and queues.
- `data/` stores pipeline artifacts and audit trails.
- `prompts/` stores AGY worker prompts so they can be versioned.

## 6. Pipeline State Store (SQLite)

`data/state.db` tracks everything needed for idempotency and dedup:

```sql
CREATE TABLE seen_items (
  item_key TEXT PRIMARY KEY,        -- normalized URL or video_id
  source_type TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,      -- UTC ISO-8601
  status TEXT NOT NULL              -- new|queued|downloaded|transcribed|drafted|published|rejected|ignored
);

CREATE TABLE published_index (
  slug TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  content_type TEXT NOT NULL,
  source_urls TEXT NOT NULL,        -- JSON array
  published_at TEXT NOT NULL
);

CREATE TABLE run_history (
  run_id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,           -- hourly|daily
  started_at TEXT NOT NULL,
  finished_at TEXT,
  result TEXT,                      -- success|failed|skipped_lock
  agy_calls INTEGER DEFAULT 0,
  error_summary TEXT
);
```

Rules:

- Normalize URLs before keying (strip tracking params, lowercase host, canonical YouTube `watch?v=` form).
- Every stage updates `seen_items.status` as it progresses; a crash mid-run resumes from status, never re-does completed work.
- `published_index` is what the validator checks for duplicate slugs/titles/source URLs.
- Keep `data/logs/run-history.jsonl` as a human-readable mirror if desired, but the DB is authoritative.

## 7. Source Registry Logic

The source registry is the central list of monitored sources. AGY is allowed to maintain it, but changes must be explicit and auditable.

Registry files:

```text
content/registry/youtube_channels.json
content/registry/news_sources.json
content/registry/reddit_sources.json
content/registry/source_changes.jsonl
```

YouTube registry entries now carry both a human channel URL and a `rss_url` feed URL so the generic ingestion helper can poll them without special-case code.

Each YouTube channel entry should include:

```json
{
  "id": "youtube_channel_id",
  "name": "Channel Name",
  "url": "https://www.youtube.com/@channel",
  "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=...",
  "category": "uap_research",
  "priority": 1,
  "active": true,
  "reason": "High-signal UFO/UAP source with recurring analysis content.",
  "evidence_urls": ["https://..."],
  "added_by": "agy",
  "added_at": "2026-07-06T00:00:00Z",
  "last_checked_at": null,
  "etag": null,
  "last_modified": null,
  "consecutive_failures": 0
}
```

Each source change must be appended to `source_changes.jsonl`:

```json
{"timestamp":"2026-07-06T00:00:00Z","action":"add","source_type":"youtube","source_id":"...","reason":"...","evidence_urls":["https://..."],"agy_run_id":"..."}
```

Rules:

- AGY may propose and apply source changes.
- Source changes take effect on the next run, not mid-run.
- Source changes require reason and evidence URL fields.
- Sources can be deactivated instead of deleted.
- The top 10 UFO/UAP YouTube channels should be maintained as a priority group, but the exact list can evolve with evidence.
- Auto-deactivate a source after 10 consecutive fetch failures and log it; AGY can propose reactivation later.

Feed politeness (applies to all fetching):

- Send a descriptive User-Agent (e.g. `UAPNewsHub/1.0 (contact URL)`). Reddit in particular blocks default/empty user agents.
- Use conditional GET with ETag/Last-Modified where the feed supports it; store the values in the registry entry.
- One fetch per source per run, with per-domain rate limiting (min 2s between requests to the same host) and exponential backoff on 429/5xx.
- For Reddit, prefer the public RSS endpoints (`https://www.reddit.com/r/<sub>/new/.rss`) over JSON scraping; they are more tolerant of unauthenticated polling. Poll no more than hourly per subreddit.

## 8. Pipeline Overview

The system has two scheduled entrypoints:

```text
Hourly Run:
  environment check
  acquire lock (with stale-lock recovery)
  source registry load
  lightweight source ingestion (conditional GETs)
  YouTube new-upload check (RSS only, no downloads)
  IF no new items: update status page timestamp, release lock, exit  <-- saves AGY quota
  breaking candidate triage (AGY, budget-capped)
  AGY short-form analysis
  deterministic validation
  site rebuild
  git publish if changed and valid
  record run in state.db

Daily Run:
  environment check
  acquire lock
  source registry maintenance via AGY
  deep source ingestion
  YouTube download queue (capped per run)
  local transcription and diarization
  media cleanup per retention policy
  AGY transcript analysis
  AGY article drafting
  AGY factual review
  deterministic validation
  claim tracker update
  site rebuild
  git publish if changed and valid
  record run in state.db
```

The hourly run should be fast, conservative, and cheap: if ingestion finds nothing new, it makes zero AGY calls. The daily run can be slower and handle long YouTube videos.

## 9. Pipeline Stage Details

### Stage 1: Environment Check

Script: `scripts/check_environment.ps1`

Check:

- `agy` exists and responds to a trivial invocation.
- `python`, `ffmpeg`, `git` exist.
- `yt-dlp` exists or the local Python package is installed.
- Required Python packages are installed (`pip check` against `requirements.txt`).
- The repo has a configured remote and non-interactive push works (`git push --dry-run`).
- `HF_TOKEN` is present in the environment if diarization is enabled.
- Free disk space on the data drive exceeds a configurable floor (default 20 GB).
- No forbidden cloud/API environment variables are required by the pipeline.

Expected behavior:

- Print safe status only. Never print secrets or token values.
- Do not call `gcloud`.
- Exit non-zero if required local tools are missing.

### Stage 2: Source Ingestion

Script: `scripts/ingest_sources.py`

Responsibilities:

- Read source registry files.
- Fetch RSS/web/public feed data for monitored sources using conditional GET and the politeness rules in Section 7.
- Collect metadata for candidate stories.
- Detect new YouTube videos by channel/feed.
- Dedup against `state.db` `seen_items` (normalized URL keys), not by scanning folders.
- Write source packets to `data/source-packets/` and insert `seen_items` rows.

Source packet shape:

```json
{
  "packet_id": "2026-07-06-youtube-channel-video-slug",
  "source_type": "youtube",
  "source_name": "Channel Name",
  "source_url": "https://www.youtube.com/watch?v=...",
  "title": "Video or Article Title",
  "published_at": "2026-07-06T12:00:00Z",
  "collected_at": "2026-07-06T13:00:00Z",
  "author_or_channel": "Channel Name",
  "raw_summary": "Metadata summary from feed or page.",
  "candidate_reason": "New video from monitored priority channel.",
  "related_urls": [],
  "status": "new"
}
```

### Stage 3: YouTube Download

Script: `scripts/download_youtube.py`

Responsibilities:

- Read new YouTube source packets with status `queued`.
- Download audio-only with `yt-dlp` (`-f bestaudio`), keeping metadata to link back to the original video.
- Store downloaded artifacts under `data/downloads/`.
- Skip anything already past `downloaded` status in `state.db`.

Hardening (this stage WILL fail intermittently — design for it):

- Cap downloads per daily run (default 5 videos, configurable). A backlog is fine; a ban is not.
- Sleep 30–120s (randomized) between downloads.
- Use `--cookies-from-browser` or a cookies file from a throwaway account if bot-check errors appear (see Phase 0 decision).
- On "Sign in to confirm you're not a bot" or HTTP 429: mark the packet `download_failed`, increment a retry counter, back off until the next daily run. After 3 failed attempts, mark `download_abandoned` and log it — never retry-loop within a run.
- Cap video length (default: skip videos over 4 hours) unless manually whitelisted; a 6-hour livestream can eat the whole transcription window.
- Keep `yt-dlp` updated (`yt-dlp -U` in the daily run) — YouTube changes break old versions regularly.

Output:

```text
data/downloads/<video_id>/
|-- metadata.json
|-- audio.wav
`-- download.log
```

Rules:

- Do not publish downloaded video/audio files.
- Do not redistribute transcripts as a substitute for the original video.
- Use transcripts internally for analysis and quote only short, relevant excerpts with source links.

### Stage 4: Local Transcription And Speaker Diarization

Script: `scripts/transcribe_diarize.py`

Use:

- `ffmpeg` for audio normalization (16 kHz mono WAV).
- `faster-whisper` for transcription (model size per the Phase 0 GPU decision).
- WhisperX or `pyannote.audio` for speaker diarization (requires the gated-model HF token from Phase 0).

Goal: produce both human-readable and structured transcripts with speaker differentiation.

Text output example:

```text
[SPEAKER_00 00:01:12-00:01:20]
We received the report from pilots near the restricted airspace.

[SPEAKER_01 00:01:21-00:01:29]
Was there radar confirmation, or only visual contact?
```

JSON output example:

```json
{
  "video_id": "abc123",
  "language": "en",
  "model": "faster-whisper-medium",
  "diarization": "whisperx-pyannote",
  "segments": [
    {
      "speaker": "SPEAKER_00",
      "start": 72.0,
      "end": 80.0,
      "text": "We received the report from pilots near the restricted airspace."
    }
  ]
}
```

Why this matters:

- Speaker labels reduce AGY confusion.
- Host, guest, narrator, caller, and quoted speaker claims can be separated.
- Article claims can cite who said something instead of treating the transcript as one anonymous voice.

Fallback rule: if diarization fails (token issue, OOM, model error) but transcription succeeded, keep the unlabeled transcript, tag the packet `diarization_failed`, and let downstream stages proceed with speaker fields set to `UNKNOWN`. The validator then requires the article to avoid speaker-attributed claims for that item. A missing speaker label should degrade the article, not kill the pipeline.

Media retention (script: `scripts/cleanup_media.py`, runs at end of daily run):

- After a transcript passes format validation, delete `audio.wav`; keep `metadata.json`, `download.log`, and all transcript artifacts forever.
- Never auto-delete transcripts, packets, AGY runs, or validation records.
- Log every deletion.

### Stage 5: AGY Source Triage

Prompt: `prompts/source_triage.md`

Input:

- Source packet JSON.
- Related metadata.
- Existing published/queued story index (from `state.db`, not folder scans).

Output:

```json
{
  "packet_id": "...",
  "decision": "publish_candidate",
  "content_type": "breaking_brief",
  "importance": "medium",
  "novelty": "new",
  "risk_level": "low",
  "reason": "New report from monitored source with clear source URL.",
  "required_sources": ["https://..."],
  "do_not_publish_reason": null
}
```

Allowed decisions:

- `ignore`
- `queue_for_daily`
- `download_transcribe`
- `publish_candidate`
- `needs_more_sources`

Batch triage: when multiple new packets exist, triage them in a single AGY call (array in, array out) rather than one call per packet. This is the single biggest AGY-quota saver in the pipeline.

### Stage 6: AGY YouTube Transcript Analysis

Prompt: `prompts/youtube_analysis.md`

Input:

- Source packet.
- YouTube metadata.
- Speaker-labeled transcript JSON/text. For very long transcripts, chunk to fit AGY context and pass a rolling summary between chunks; store the chunking decision in the run record.

Output:

```json
{
  "packet_id": "...",
  "video_id": "...",
  "summary": "Concise transcript-grounded summary.",
  "speakers": [
    {"speaker": "SPEAKER_00", "likely_role": "host", "confidence": "medium"}
  ],
  "key_claims": [
    {
      "claim": "A guest stated that a pilot report described unusual lights near restricted airspace.",
      "speaker": "SPEAKER_01",
      "timestamp_start": "00:13:04",
      "timestamp_end": "00:13:42",
      "claim_type": "reported_claim",
      "support_level": "transcript_only",
      "source_url": "https://www.youtube.com/watch?v=..."
    }
  ],
  "article_recommendation": "draft_youtube_intel",
  "publication_risk": "medium",
  "open_questions": ["Was there a primary document or only verbal reporting?"]
}
```

### Stage 7: AGY Article Drafting

Prompt: `prompts/article_draft.md`

Input:

- Triage output.
- Transcript analysis if available.
- Source packet.
- Existing related claims/articles.

Output:

```json
{
  "slug": "short-url-safe-slug",
  "title": "Evidence-First Headline",
  "dek": "One-sentence article summary.",
  "content_type": "youtube_intel",
  "confidence": "medium",
  "claim_labels": ["reported_claim", "analysis"],
  "sources": [
    {"title": "Original video", "url": "https://www.youtube.com/watch?v=...", "type": "primary"}
  ],
  "article_markdown": "# Title\n\nArticle body...",
  "related_claims": [],
  "should_publish": true
}
```

Drafting rules:

- Do not invent facts.
- Do not imply confirmation unless a primary source confirms it.
- Use "reported", "claimed", "said", or "according to" where appropriate.
- Include sources in the article body and metadata.
- Prefer concise analysis over long filler.
- Do not publish raw transcripts. Direct quotes from a transcript must be short excerpts (guideline: under 75 words each, and a small fraction of the total transcript) with a timestamped link to the original video.

### Stage 8: AGY Factual Review

Prompt: `prompts/factual_review.md`

Input:

- Draft article JSON.
- Source packet.
- Transcript analysis.
- Source URLs.

Output:

```json
{
  "review_result": "pass",
  "blocking_issues": [],
  "non_blocking_warnings": ["Only one primary source is available."],
  "required_edits": [],
  "confidence_after_review": "medium"
}
```

Allowed review results:

- `pass`
- `revise`
- `reject`

Only `pass` may continue to deterministic validation. A `revise` result gets exactly one redraft-and-re-review cycle; if it does not pass on the second review, reject it to `content/rejected/`. Unbounded revise loops burn quota and never converge.

### Stage 9: Deterministic Validation

Script: `scripts/validate_outputs.py`

Validation must not rely on AGY judgment. Validate every stage output against its file in `schemas/` using `jsonschema` first, then apply content rules.

Reject if:

- JSON fails schema validation (missing fields, wrong types, unknown enum values).
- Article Markdown is empty.
- No source URL exists, or any source URL is not a syntactically valid absolute `https` URL.
- A YouTube-derived story has no transcript artifact on disk.
- A transcript-derived claim has no timestamp, or the timestamp exceeds the video duration in `metadata.json`.
- A speaker-attributed claim exists for an item tagged `diarization_failed`.
- `confidence` is not one of `low`, `medium`, `high`.
- `content_type` is not an allowed value.
- The same source URL was already published (checked against `published_index`).
- The title or slug duplicates an existing article.
- Article includes forbidden overclaiming language such as "proves aliens", "confirmed alien", "irrefutable evidence" without explicit source/evidence labels (maintain the phrase list in a versioned config file, not hardcoded).
- A direct transcript quote exceeds the excerpt length limit.
- Review result is not `pass`.

Allowed content types:

- `latest_briefing`
- `breaking_watch`
- `youtube_intel`
- `source_digest`
- `claim_tracker`

Allowed claim labels:

- `confirmed_fact`
- `reported_claim`
- `witness_account`
- `official_statement`
- `analysis`
- `speculation`
- `unverified`

Every validation run writes a result record to `data/validation/<packet_id>.json` including pass/fail, rule hits, and timestamps.

### Stage 10: Site Build

Script: `scripts/build_site.py`

Responsibilities:

- Convert validated content JSON/Markdown into static HTML via Jinja2 templates in `templates/`.
- Generate index pages for all site sections, plus `status.html`.
- Generate source panels and confidence badges.
- Generate RSS feed and sitemap.
- Emit `.nojekyll` so GitHub Pages serves files verbatim.
- Preserve source links on every article page.

Determinism rules (so diffs stay readable and rebuilds are comparable):

- Sort all iteration orders explicitly (by slug, by date).
- Serialize JSON with sorted keys and fixed separators.
- No "generated at" timestamps inside article pages; the only timestamps that change per-build live on `status.html`.
- A rebuild with unchanged content must produce byte-identical output. Add a golden-file test for this.

### Stage 11: GitHub Pages Publish

Script: `scripts/publish_github_pages.ps1`

Responsibilities:

- Run validation before publishing.
- Run site build.
- Check for generated changes.
- Commit source/content changes to `main`.
- Deploy `site/` to the `gh-pages` branch as a single squashed commit (`git worktree` or a temp clone; force-push). This keeps generated-HTML history out of `main` and holds repo size flat.

Commit message format:

```text
publish: update UFO news hub YYYY-MM-DD HHmm
```

Rules:

- Do not push if validation fails.
- Do not push if build fails.
- Do not push if `main` status includes unexpected non-generated changes (fail closed and alert).
- Log publish success or failure to `data/logs/publish.log` and `run_history`.

## 10. AGY Usage Model

Use AGY as a constrained worker, not as an unrestricted site operator.

Recommended invocation pattern:

```powershell
agy --print "<prompt text here>" --add-dir . --print-timeout 10m
```

Worker wrapper script: `scripts/run_agy_worker.py`

Wrapper responsibilities:

- Load prompt file.
- Inject source packet path and output schema.
- Run `agy --print` with the prompt immediately after `--print`, followed by flags such as `--add-dir` and `--print-timeout`.
- For large transcript prompts, write the prompt to `data/agy-prompts/` and pass AGY a short instruction pointing at the prompt file.
- Run with a hard subprocess timeout (default 12m — slightly above `--print-timeout` so the wrapper always wins).
- Save raw AGY response to `data/agy-runs/<run_id>/raw.txt`.
- Extract/validate JSON response against the stage schema.
- Save parsed response to `data/agy-runs/<run_id>/parsed.json`.
- Never let AGY directly publish without deterministic validation.

Budget guard:

- Hourly run: max 3 AGY calls. Daily run: max 25 AGY calls (tune after observing real usage).
- Count every call in `run_history.agy_calls`.
- If the budget is hit, remaining packets stay queued for the next run. Never trade validation calls for drafting calls.
- If AGY itself is unavailable (auth expired, rate-limited, binary missing), the run fails closed: log, alert, exit non-zero. Do not fall back to publishing unreviewed content.

Tips:

- Keep each AGY task narrow.
- Prefer separate prompts over one large autonomous prompt, but batch homogeneous work (triage) into single calls.
- Include exact output schema in every prompt.
- Include "return JSON only, no markdown fences, no preamble" for structured stages.
- Save every prompt and response for debugging.
- If AGY output is malformed, retry once with a repair prompt, then reject.

## 11. Scheduling Logic

Use Windows Task Scheduler.

Hourly task:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\run_hourly.ps1
```

Daily task:

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\run_daily.ps1
```

Task settings: "Run whether user is logged on or not", "Do not start a new instance" as a second layer behind the lock file, random start delay of a few minutes so hourly/daily tasks don't collide at midnight.

Lock handling:

- Lock file contains PID and start timestamp.
- On startup, if a lock exists: if the PID is no longer running OR the lock is older than a max-age (hourly: 55 min; daily: 6 hours), treat it as stale, log the recovery, delete it, and proceed. Otherwise exit cleanly with `skipped_lock`.
- Always remove the lock in a `finally` block.

Failure alerting (`scripts/notify_failure.ps1`):

- On any failed run: write the failure to `run_history`, raise a Windows toast notification, and append to `data/logs/failures.log`.
- The public `status.html` timestamps are the backstop — check the site occasionally; stale timestamps mean silent failure.
- Optional later upgrade: a free-tier webhook (Discord/ntfy.sh) — plain HTTP POST, no paid API.

Scheduler safety:

- Store logs for every run.
- Never delete source artifacts automatically (media cleanup in Stage 4 is the only sanctioned deletion).

## 12. Local Whisper/Diarization Notes

Whisper-style transcription alone does not reliably identify speakers. Use diarization to label speakers and reduce article errors.

Recommended local stack:

- `faster-whisper` for transcription.
- WhisperX for alignment and speaker diarization when practical.
- `pyannote.audio` as the diarization backend where required.

Hard requirements and realities:

- pyannote models are gated on Hugging Face: accept the license and pass `HF_TOKEN` (Phase 0). Without it, diarization fails at model load.
- GPU vs CPU is the dominant cost factor. Budget roughly: GPU (`large-v3`) ≈ minutes per hour of audio; CPU (`medium`) can approach real-time or slower. Size the daily download cap to what the box can actually transcribe overnight.
- Long-audio diarization is memory-hungry; if OOM occurs, chunk audio into 30–60 min segments and merge speaker labels, or fall back to transcription-only per the Stage 4 fallback rule.

Implementation tips:

- Store raw transcript and speaker-labeled transcript.
- Keep segment timestamps.
- Include speaker labels in AGY input.
- Ask AGY to infer roles carefully: host, guest, caller, narrator, unknown.
- Treat speaker roles as uncertain unless obvious from the transcript.
- Do not present inferred speaker roles as confirmed facts.

## 13. Editorial Rules

Every article should include:

- Title.
- Dek/summary.
- Publication time.
- Source list.
- Confidence label.
- Claim labels.
- Body content.
- "What is known" section.
- "What is claimed" section when applicable.
- "Evidence and sources" section.
- "Open questions" section when useful.

Article language rules:

- Use "reported" for reports.
- Use "claimed" for claims.
- Use "said" for direct source statements.
- Use "according to" when attributing to a source.
- Avoid "confirmed" unless a primary source confirms it.
- Avoid "proof" unless the article is literally about proof standards.
- Avoid presenting speculation as fact.

## 14. Claim Tracker Data Model

Claim records live in `content/claims/<claim_id>.json` and validate against `schemas/claim.schema.json`:

```json
{
  "claim_id": "2026-restricted-airspace-lights",
  "topic": "Restricted airspace light sightings",
  "statement": "Pilots reported unusual lights near restricted airspace in mid-2026.",
  "status": "open",
  "confidence": "low",
  "first_reported_at": "2026-07-06T00:00:00Z",
  "last_updated_at": "2026-07-06T00:00:00Z",
  "evidence": [
    {
      "date": "2026-07-06",
      "source_url": "https://...",
      "evidence_type": "reported_claim",
      "effect": "supports",
      "note": "Initial video discussion; verbal report only."
    }
  ],
  "related_articles": ["slug-one", "slug-two"],
  "assessment_history": [
    {"date": "2026-07-06", "confidence": "low", "reason": "Single verbal source."}
  ]
}
```

Rules:

- `status` is one of `open`, `developing`, `resolved_supported`, `resolved_unsupported`, `stale`.
- `effect` is one of `supports`, `contradicts`, `context`.
- Confidence may only change when a new evidence entry is added; every change appends to `assessment_history`.
- `scripts/update_claims.py` merges validated article claims into claim records deterministically (AGY proposes claim linkage; the script applies it and enforces the schema).
- Claims untouched for 90 days are auto-marked `stale` on the site, not deleted.

## 15. Data Retention And Auditability

Keep forever:

- Source packets.
- Download metadata.
- Transcript JSON/text.
- AGY prompts, raw outputs, and parsed outputs.
- Validation results.
- Final content files.
- Published HTML (in `gh-pages` history / latest deploy).

Delete per policy:

- `audio.wav` after its transcript passes format validation (Stage 4 cleanup).

Never publish:

- Full downloaded video.
- Full raw audio.
- Full transcript as standalone content.
- Any credential, token, cookie file, or local account state.

## 16. Implementation Phases

### Phase 0: Prerequisites (see Section 0)

- [ ] HF account, gated-model license acceptance, token stored locally.
- [ ] GPU check and whisper model size decision.
- [ ] GitHub Pages branch strategy decided (`gh-pages` recommended).
- [ ] Non-interactive git push verified.
- [ ] YouTube cookies decision made.
- [ ] UTC timestamp standard acknowledged in README.

### Phase 1: Project Foundation

- [ ] Create repo skeleton and folder layout.
- [ ] Add README with local-only/no-paid-API rule and setup steps.
- [ ] Add `.gitignore` for downloads, logs, local caches, `site/`, `.env`, and large media.
- [ ] Add `.env.example` and `requirements.txt`.
- [ ] Add environment checker.
- [ ] Add SQLite state store with schema migration on first run.
- [ ] Add basic static site shell and Jinja2 templates.
- [ ] Add local build command.

### Phase 2: Source Registry And Ingestion

- [ ] Add source registry JSON files.
- [ ] Add source-change JSONL logging.
- [ ] Add RSS/public-feed ingestion with conditional GET and rate limiting.
- [ ] Add URL normalization and state-DB dedup.
- [ ] Add source packet writer.
- [ ] Add auto-deactivation after consecutive failures.
- [ ] Add ingestion fixture tests.

### Phase 3: YouTube Download And Transcription

- [ ] Install or vendor `yt-dlp`; add self-update to daily run.
- [x] Add YouTube download script with per-run cap, randomized delays, retry/abandon logic.
- [x] Add audio normalization.
- [x] Add `faster-whisper` transcription.
- [ ] Add WhisperX/pyannote speaker diarization path with HF token and OOM/failure fallback.
- [ ] Add media cleanup script.
- [x] Add transcript format tests.

### Phase 4: AGY Worker System

- [x] Add prompt files.
- [x] Add jsonschema files for every stage output.
- [x] Add AGY wrapper script with hard timeout and call counting.
- [x] Add budget guard.
- [x] Save raw and parsed AGY outputs.
- [x] Add JSON extraction and repair-once logic.
- [x] Add batch triage (multiple packets per call).
- [x] Add fixture tests for malformed AGY output handling.

### Phase 5: Editorial Validation

- [x] Wire jsonschema validation for all stage outputs.
- [x] Add content validator rules (sources, timestamps, quote length, diarization-failure speaker rule).
- [x] Add duplicate source/slug checks against `published_index`.
- [x] Add overclaiming language checks with versioned phrase list.
- [x] Add tests for accepted and rejected articles.

### Phase 6: Static Site Build

- [x] Build index page.
- [x] Build article pages.
- [x] Build section index pages for currently populated content types.
- [x] Build status page.
- [x] Add RSS feed, sitemap, `.nojekyll`, and meta/OG tags.
- [x] Add professional intelligence-briefing theme.
- [x] Add golden-file determinism test (rebuild == byte-identical).
- [ ] Add richer dedicated layouts for Breaking Watch, YouTube Intel, Source Digest, and Claim Tracker once those lanes have real content.

### Phase 7: Scheduling And Publishing

- [ ] Add hourly runner with early-exit when nothing is new.
- [ ] Add daily runner.
- [ ] Add lock-file protection with stale-lock recovery.
- [ ] Add failure notification script.
- [x] Add validated publish helper with fail-closed dirty-source guard.
- [ ] Replace local `_gh_pages` staging copy with `gh-pages` squash deploy.
- [ ] Add dry-run mode.
- [ ] Add Task Scheduler installer script.
- [ ] Test local run before enabling auto-push.

### Phase 8: First Live Content Run

- [ ] Run environment check.
- [ ] Run source ingestion.
- [ ] Run one YouTube download/transcription.
- [ ] Run AGY analysis and draft generation.
- [ ] Validate output.
- [ ] Build site locally and inspect generated pages.
- [ ] Commit and deploy to GitHub Pages.
- [ ] Confirm status page timestamps update.

### Phase 9: Supervised Autonomy (one week)

- [ ] Enable scheduled tasks with auto-push OFF (dry-run publish).
- [ ] Review every drafted/rejected item daily for one week.
- [ ] Review every AGY-proposed source change manually.
- [ ] Tune budget caps, download caps, and validator phrase list from real behavior.
- [ ] Only then enable auto-push.

## 17. Testing Plan

Test without live paid APIs.

Required tests:

- Environment checker detects missing `agy`, `ffmpeg`, `yt-dlp` or Python `yt_dlp`, Python packages, and `HF_TOKEN` when diarization is enabled.
- Ingestion writes valid source packets from fixture feeds.
- URL normalization collapses tracking-param and format variants to one key.
- Duplicate detection prevents duplicate packets (state-DB backed).
- Transcript parser accepts speaker-labeled transcript JSON and unlabeled fallback JSON.
- Validator rejects: missing sources, missing timestamps on transcript claims, timestamps beyond video duration, malformed AGY JSON, duplicate source URLs, over-length quotes, speaker attribution on diarization-failed items.
- Site builder creates article HTML with source links.
- Site builder is deterministic: two builds from identical content are byte-identical (golden-file test).
- Publish script refuses to push when validation fails.
- Publish script refuses to proceed when unexpected dirty source changes are present.
- Stale lock is recovered; live lock causes clean `skipped_lock` exit.
- Budget guard stops AGY calls at the cap and requeues remaining packets.

Manual smoke tests:

- Run `scripts/check_environment.ps1`.
- Run one fixture ingestion.
- Run one real YouTube download/transcription.
- Run one AGY worker against a saved packet.
- Build site locally and open `site/index.html`.
- Review the rough draft at `site/articles/rough-draft-uap-evidence-standards.html`.
- Confirm every article has source links and confidence labels.
- Kill a run mid-flight and confirm the next run recovers (stale lock + resume from `seen_items` status).

## 18. Operational Tips

- Start with a small source registry (5–10 sources) before letting AGY expand it.
- Keep downloaded media out of git.
- Keep transcripts local and publish only short excerpts.
- Run hourly checks conservatively; use daily runs for deeper analysis.
- Review the first several AGY-maintained source changes manually before trusting the schedule (formalized as Phase 9).
- If AGY starts producing vague or sensational content, tighten prompts and validators before adding sources.
- Prefer queueing uncertain content over publishing it.
- Watch `status.html` — stale timestamps are the silent-failure alarm.
- Keep generated pages deterministic so diffs show meaningful changes.
- Check disk usage monthly; transcripts and AGY-run archives grow slowly but forever.

## 19. Acceptance Criteria

The system is ready for autonomous operation when:

- A full daily run completes without paid API calls.
- One YouTube video is downloaded, transcribed, speaker-labeled, analyzed, validated, and published as a YouTube Intel article.
- One non-YouTube source item is ingested, drafted, validated, and published.
- A malformed or unsupported AGY article is rejected and stored in `content/rejected/`.
- A simulated bot-check download failure is retried, then abandoned, without stalling the run.
- A killed run is recovered by the next run (stale lock + status resume) with no duplicate work.
- GitHub Pages receives an auto-deployed generated site update on `gh-pages` and `main` history contains no generated HTML.
- The published pages show source URLs, confidence labels, and claim labels; `status.html` shows current run timestamps.
- The run leaves an audit trail in `data/source-packets/`, `data/transcripts/`, `data/agy-runs/`, `data/validation/`, and `state.db`.
- Phase 9 supervised week completed with manual review of all source changes.

## 20. Known Risks And Honest Tradeoffs

- **YouTube is the fragile link.** Bot detection, throttling, and yt-dlp breakage are when, not if. The caps, delays, cookies plan, and abandon logic contain the damage but don't eliminate it. Expect occasional gaps in YouTube Intel.
- **Quoting/transcript legality is a judgment call.** Short attributed excerpts with links are standard practice, but this plan is not legal advice. The excerpt limits keep the site clearly transformative-analysis-shaped rather than transcript-mirror-shaped.
- **AGY quota is a real ceiling.** An hourly + daily schedule with review passes can consume meaningful quota. The early-exit hourly run, batch triage, and budget caps are load-bearing, not optional.
- **CPU-only transcription may not keep up.** If there's no GPU, either the download cap stays very low or accuracy drops with smaller models. Measure real throughput in Phase 3 before setting the cap.
- **Autonomous editorial systems drift.** Validators catch structural failures, not slow tonal drift toward sensationalism. Phase 9's supervised week plus occasional spot checks are the only real countermeasure.
- **Niche credibility risk.** UFO/UAP content attracts low-quality sources. The registry evidence requirements and manual review of AGY source additions are the firewall; loosening them is the fastest way to become the rumor blog this plan explicitly avoids.

## 21. Final Implementation Notes

Build this in small working slices. Do not start with the whole autonomous system. The first useful milestone is a local static site plus one manually triggered pipeline run that produces one validated article from one source packet. After that works, add YouTube transcription, then AGY source maintenance, then scheduler automation, then GitHub Pages auto-publishing — and only after the Phase 9 supervised week, full autonomy.

The most important engineering rule is separation of responsibilities:

- Scripts collect, normalize, validate, build, and publish.
- AGY searches, reasons, writes, and reviews.
- Validators decide whether AGY output is safe to publish.
- The state database decides what has already been done.
- GitHub Pages serves only generated public files.
