# Interrogation Pipeline

Daily YouTube case-mining pipeline + local web dashboard for the FOIA / true-crime workflow.

Cross-platform Python + React app. Discovers new uploads on a curated channel list via RSS, downloads English captions through Webshare residential proxies + yt-dlp, scans transcripts with Claude Haiku 4.5 to surface homicide cases, fact-checks names via Tavily, dedupes against your Trello board, and gives you a one-click "Send to Trello" workflow.

## Quick start

| OS | Install command |
|---|---|
| **macOS / Linux** | `bash ./install.sh` |
| **Windows** | `powershell -ExecutionPolicy Bypass -File .\install.ps1` |

Then:

1. Edit `backend/.env` and add your API keys (Anthropic, Tavily, Trello, Webshare).
2. Drop a YouTube cookies file at `backend/data/cookies/cookies_p4.txt`.
3. Start: `cd backend && ./.venv/bin/python -m interrogation_pipeline` (Windows: `.\.venv\Scripts\python.exe -m interrogation_pipeline`).
4. Open <http://localhost:8765>.

Full instructions: see [ONBOARDING.md](ONBOARDING.md) (or the printable [ONBOARDING.html](ONBOARDING.html)).

## What you get

- **Today** — accepted cases as cards with Send-to-Trello button; collapsed rejected list at the bottom.
- **Calendar** — month grid color-coded by activity.
- **Channels** — toggle channels on/off, move them between pipelines, add new ones.
- **Runs** — every run with status, counts, and an event log.
- **Settings** — schedule, lookback hours, concurrency, banned-state list, Trello board IDs.
- **Stats** — Anthropic spend (today / week / month / lifetime) + per-channel coverage.

## What's in the box

```
.
├── ONBOARDING.md / .html       Read-once setup + usage doc
├── BUILD_PLAN_FOR_AYUSH.md     Original architectural pitch
├── CLAUDE_PROMPT.md            Paste into Claude Code if you want AI help installing
├── install.sh / install.ps1    One-command installer
├── Makefile                    `make install / build / run / test / clean`
├── docs/superpowers/specs/     Locked design spec
├── backend/                    FastAPI + APScheduler + SQLite + SQLAlchemy
│   ├── interrogation_pipeline/
│   │   ├── store/              SQLAlchemy models + repos
│   │   ├── config/             env settings + runtime config table
│   │   ├── discovery/          YouTube RSS parser
│   │   ├── scrape/             yt-dlp wrapper + Webshare proxy pool
│   │   ├── scan/               VTT cleaner + Haiku scanner
│   │   ├── verify/             Tavily + Haiku name corrector
│   │   ├── dedup/              Multi-field fuzzy match
│   │   ├── trello/             Async REST client + card formatter
│   │   ├── scheduler/          APScheduler thread + run orchestrator
│   │   ├── api/                FastAPI app + routers + SSE stream
│   │   └── prompts/            Haiku prompts (verbatim from spec)
│   ├── tests/                  58 unit tests, hermetic
│   └── pyproject.toml
└── frontend/                   React 19 + Vite + Tailwind v4 + react-query
    ├── src/
    │   ├── pages/              Today, Calendar, Channels, Runs, Settings, Stats
    │   ├── components/         StatsBar, CaseCard, RejectedRow, HealthBanner
    │   ├── api/                Typed client + types
    │   └── lib/                useRunStream (SSE), formatters
    └── package.json
```

## Costs (typical operation)

For ~100 unique homicide cases per day (means scanning ~400 transcripts):
- Anthropic Haiku scans: ~$2.80/day
- Tavily + Haiku verify on accepted cases: ~$1.20/day
- Webshare bandwidth: ~$0.04/day (covered by $27.50/mo plan)
- Trello: free
- **Total: ~$120/month** at full volume

## License

Private. All rights reserved.
