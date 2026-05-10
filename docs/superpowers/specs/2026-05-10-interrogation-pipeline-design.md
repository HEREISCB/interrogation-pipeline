# Interrogation Pipeline — Design Spec

**Author:** Chaitanya
**Client:** Ayush
**Date:** 2026-05-10
**Status:** Approved (sections 1–5 explicitly; 6–7 implicitly during build)

## 1. Goal

Cross-platform Python web app that:
1. Discovers new YouTube videos on Ayush's P4 "snipe" channels each day via RSS.
2. Downloads only new captions through Webshare residential proxies via yt-dlp.
3. Scans transcripts with Claude Haiku 4.5 using the homicide-only prompt (`Prompt.pdf`).
4. Verifies/corrects defendant names via Tavily + Haiku.
5. Dedupes against both Ayush's existing `FOIA Trials` Trello board AND a new triage board.
6. Surfaces results on a local dashboard with one-click "Send to new Trello board".
7. Shows rejected cases at the bottom of the dashboard so the human can spot AI mistakes.
8. Self-heals: per-video proxy retries, daily re-queue of failed videos, weekly reconciliation sweep.

## 2. Architecture

- **One repo, two trees**: `backend/` (Python 3.12, FastAPI, async), `frontend/` (React + Vite).
- **One process**: `python -m interrogation_pipeline` runs APScheduler thread + serves API + serves built frontend at `http://localhost:8765`.
- **State**: single SQLite file (`data/state.db`) accessed only via SQLAlchemy.
- **External services**: YouTube RSS (free, no auth), Webshare residential proxies, Anthropic Haiku 4.5, Tavily, Trello.
- **Auth**: none in v1, `bind 127.0.0.1`.

## 3. Modules (backend)

| Module | Job |
|---|---|
| `store/` | SQLAlchemy ORM, async session factory, repos. Only path to the DB. |
| `config/` | Env vars (API keys) + `config` table (schedule, board IDs, concurrency). |
| `discovery/` | `rss.py`: `fetch_recent_videos(channel_id, since_iso) -> list[VideoStub]`. |
| `scrape/` | `ytdlp.py` (subprocess wrapper, `--extractor-args 'youtube:player_client=tv'`, `--no-check-certificates`, `--cookies`, 120s timeout); `proxies.py` (Webshare session pool, 30-min blacklist on rate-limit); `errors.py` (typed errors). |
| `scan/` | `vtt.py` cleaner; `scanner.py` calls Haiku with prompt from `prompts/scan.txt` (the v2 HOMICIDE prompt with additive drama rubric); pydantic-typed result. |
| `verify/` | Tavily search + Haiku verifier; per-query cache. |
| `dedup/` | `fuzzy.py` (rapidfuzz, defendant ≥85% required + 2 of 3 of victim/state/year); `dedup_engine.py` cross-references Trello card cache. |
| `trello/` | Async client, paginated card fetch, card description formatter. |
| `scheduler/` | APScheduler thread; `runner.py` orchestrates discover → scrape → scan → verify → dedup. |
| `api/` | FastAPI routers (today, days, cases, channels, runs, settings, stats, SSE). |

## 4. Data flow (one daily run)

```
Requeue failed videos (attempts < 5)
  → Discovery: RSS per channel, 24h lookback, INSERT OR IGNORE on video PK
  → Scrape: per-video proxy rotation (concurrency 3), classify outcome
  → Scan: Haiku per captioned video (concurrency 5), store all results (incl. rejected)
  → Verify: Tavily + Haiku per accepted case (concurrency 3), apply name corrections
  → Internal dedup: fuzzy-match within today's verified cases
  → External dedup: fuzzy-match against cached Trello cards (old + new boards)
  → Mark all surviving cases pending_review
  → Finalize RunLog
```

User-driven actions (review time): Send to Trello (last-mile dedup → create card), Skip, Mark reviewed, Override-rejection (re-queue scan).

## 5. Schema (SQLite)

Tables: `channels`, `videos`, `scan_results`, `cases`, `case_videos`, `runs`, `run_events`, `trello_push_log`, `trello_card_cache`, `proxy_blacklist`, `tavily_cache`, `config`. See conversation history for column definitions; key invariants:

- `videos.id` is the YouTube video ID (PK) → re-discovery is free `INSERT OR IGNORE`.
- `scan_results` is append-only; rejected scans are kept for the dashboard.
- `cases` is the dedup unit; `case_videos` is the many-to-many link.
- All timestamps are UTC ISO-8601; frontend formats to IST for display only.
- `channels.youtube_total_count` updated daily by yt-dlp `--flat-playlist --simulate` (cheap).
- `channels.last_seen_iso` only advances on successful RSS reads.

## 6. API contract

REST + JSON; SSE for live run progress at `/api/runs/current/stream`. Endpoints (see chat history for full list):

- Today/Calendar: `GET /api/today`, `GET /api/days?from=&to=`
- Cases: `GET /:id`, `POST /:id/push-to-trello`, `POST /:id/skip`, `POST /:id/mark-reviewed`, `POST /:id/override-rejection`, `GET /:id/transcript`
- Stats: `GET /api/stats/p4`, `GET /api/stats/channels`
- Channels: `GET / POST / PATCH / DELETE`, `POST /:id/refresh`
- Runs: `GET /api/runs`, `GET /:id`, `GET /:id/events`, `POST /api/runs/trigger`, `POST /:id/cancel`
- Settings: `GET / PATCH`, `GET /api-keys/status`

## 7. Frontend pages

- **Today** — stats bar, accepted cases (green), rejected cases (collapsed yellow at bottom), red banner row for Tier 3 errors.
- **Calendar** — month grid, color by activity, click → day drilldown.
- **Channels** — table with pipeline dropdown, active toggle, add/remove, per-channel coverage.
- **Runs** — run history with status, counts, error breakdown, event log drilldown.
- **Settings** — schedule, lookback hours, board IDs, API key health.
- **Stats** — costs this week, AI override rate, per-channel coverage.

## 8. Error handling

Three tiers documented in chat:

- **Tier 1 (transient, per-video)**: rate-limit / bot-detection / timeout / Haiku JSON parse → retry with backoff and proxy rotation; max attempts 5 then `failed`, surfaces in next-run requeue.
- **Tier 2 (permanent, per-video)**: members-only / no-captions / DRM / age-restricted / private-or-deleted → `archived` with reason; never retried; visible on Channels page.
- **Tier 3 (run-level)**: API credit exhaustion / cookies expired / DB locked → red dashboard banner; partial-success state preserved; scheduler stays alive.

"Zero missed videos" guaranteed by three layers: per-run requeue, 24h discovery lookback, weekly `coverage_check` reconciliation sweep.

## 9. Testing

- Unit tests: hermetic, in-memory SQLite, fixtures for RSS XML / yt-dlp stderr / Haiku responses / VTT files.
- Integration tests: full daily run with all externals mocked; failure injection; idempotency.
- Smoke tests (gated, real services, opt-in): one-shot RSS / Anthropic / Tavily / Trello / yt-dlp.
- Frontend: Vitest for component logic, one Playwright happy-path.

## 10. Deployment

- Install: clone repo, `pip install -e .` (creates `interrogation_pipeline` entrypoint), one-time `npm install && npm run build` in `frontend/` (built static served by FastAPI).
- Run: `interrogation_pipeline` → opens `http://localhost:8765`. APScheduler thread inside the same process.
- Config: `.env` for secrets (Anthropic, Tavily, Trello, Webshare); `config` table for behavior tunables (editable in Settings UI).
- Data: `data/state.db` + `data/transcripts/` + `data/cookies/`. Back up by copying the data folder.

## 11. Out of scope (v1)

Whisper, email/Slack alerts, multi-user/auth, mobile, P1/P2/P3 (P4 only).

## 12. Open items resolved during conversation

- Approach: Approach 3 (FastAPI + React) chosen by Ayush over the recommended single-process simpler shape.
- Discovery: RSS for new-video detection, yt-dlp only for caption download (Section 14.3 of the handoff confirmed this).
- Dedup target: both old and new Trello boards.
- Initial scope: P4 only.
- Push to Trello: manual one-click, never automatic.
- Calendar view + progress log + rejected list at bottom: explicitly added.
- Channel pipeline dropdown + active toggle on dashboard: explicitly added.
- Timezone fix: UTC internally, configurable lookback (default 24h).
