# Interrogation Pipeline

Daily YouTube case-mining pipeline + local web dashboard.

## Quick start

```bash
# 1. Install backend (Python 3.11+)
cd backend
python -m venv .venv
. .venv/Scripts/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
                                  # Mac/Linux:        source .venv/bin/activate
pip install -e ".[dev]"

# 2. Build frontend (one-time, requires Node 20+)
cd ../frontend
npm install
npm run build                     # outputs to ../backend/interrogation_pipeline/static/

# 3. Configure secrets
cd ../backend
cp .env.example .env              # then edit .env

# 4. Run
interrogation-pipeline
# → http://localhost:8765
```

## Daily operation

The scheduler thread starts inside the same process. Default cron `0 20 * * *` (8 PM local). Edit on the Settings page or via `PIPELINE_SCHEDULE_CRON` env var.

## Layout

```
backend/
  interrogation_pipeline/
    store/        SQLAlchemy ORM, repos
    config/       env + config-table loader
    discovery/    YouTube RSS fetch
    scrape/       yt-dlp wrapper, Webshare proxy pool
    scan/         VTT cleaner, Haiku scanner
    verify/       Tavily + Haiku name verifier
    dedup/        rapidfuzz multi-field match
    trello/       client + card formatter
    scheduler/    APScheduler + run orchestrator
    api/          FastAPI routers
    prompts/      Haiku prompt templates
    static/       built frontend (created by npm run build)
  tests/
    unit/         hermetic, in-memory SQLite
    integration/  full run with externals mocked
    smoke/        opt-in real-API tests   (pytest -m smoke)
    fixtures/     RSS XML, yt-dlp stderr, VTT, Haiku response samples
  data/
    state.db          (gitignored)
    transcripts/      (gitignored)
    cookies/          (gitignored — drop your cookies_p4.txt here)
```

## Tests

```bash
pytest                   # unit + integration (no external services)
pytest -m smoke          # opt-in real-API smoke tests (costs a few cents)
pytest --cov             # with coverage
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Anthropic credit exhausted` banner | Top up at https://console.anthropic.com |
| `Webshare HTTP 402` banner | Top up bandwidth at https://dashboard.webshare.io |
| `Cookies stale` banner | Re-export `cookies_p4.txt` from a logged-in YouTube tab using the "Get cookies.txt LOCALLY" Chrome extension |
| Scheduler not firing | Check `PIPELINE_SCHEDULE_CRON` and Settings → Schedule |
| Dashboard blank | `npm run build` in `frontend/` and restart |
