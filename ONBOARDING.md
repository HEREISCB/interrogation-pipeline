# Interrogation Pipeline — Onboarding for Ayush

**By:** Chaitanya
**Last updated:** 2026-05-10

This is the only doc you need to get the pipeline running on your Mac (or any Windows box) and use it day-to-day. Read it once end-to-end — it's short.

> **Note:** the repo includes a working `.env.example` with placeholders only. You use your own Anthropic / Tavily / Trello / Webshare accounts — nothing in here is bound to my account. If you cloned the repo on a different machine than where I tested, the `.env` file won't exist yet and the install script creates it from `.env.example`.

## TL;DR — easy path (double-click)

| OS | Double-click |
|---|---|
| **Windows** | `start.bat` |
| **macOS** | `start.command` (right-click → Open the first time, macOS asks for confirmation) |

The launcher will:
1. Check that Python + Node are installed (links you to downloads if not)
2. Run first-time setup if `.venv` is missing (~2-3 min)
3. Build the dashboard if missing
4. Create `backend/.env` from the template and open it for you to paste your API keys
5. Start the server, open the dashboard in your browser

After that, the same launcher just starts the server + opens the browser. To stop: press `Ctrl+C` in the launcher window.

## TL;DR — terminal path

```
1. install everything       → run install.sh / install.ps1
2. add your API keys         → edit backend/.env
3. drop your YT cookies      → backend/data/cookies/cookies_p4.txt
4. start the server          → cd backend && ./.venv/bin/python -m interrogation_pipeline
5. open browser              → http://localhost:8765
6. click "Run now"           → watch the dashboard fill with cases
7. push the good ones        → "Send to Trello" button on each case card
```

That's the whole thing. Everything below is what to do when something doesn't behave.

---

## Install (one-time setup)

Make sure you have:

- **Python 3.11+** — check with `python3 --version`
- **Node 20+** — check with `node --version` (needed both for the dashboard build AND for yt-dlp's JS challenge solver at runtime — don't skip)
- **ffmpeg** (optional but useful for future Whisper work)

Then from the project root:

| OS | Command |
|---|---|
| **macOS / Linux** | `bash ./install.sh` |
| **Windows** | `powershell -ExecutionPolicy Bypass -File .\install.ps1` |

The script:
1. Creates `backend/.venv`, installs Python deps
2. Runs `npm install` + `npm run build` in `frontend/`, drops the static files into the backend's `static/` folder
3. Copies `backend/.env.example` to `backend/.env` (only if missing)

Re-running the script is safe — it skips work that's already done.

## Configuration — `backend/.env`

Open `backend/.env` and fill in the real values:

```ini
ANTHROPIC_API_KEY=sk-ant-...                # your Anthropic key
TAVILY_API_KEY=tvly-...                     # your Tavily key
TRELLO_API_KEY=...                          # from https://trello.com/power-ups/admin
TRELLO_TOKEN=...                            # see "Getting a Trello token" below
TRELLO_OLD_BOARD_ID=...                     # FOIA Trials board ID (for dedup)
TRELLO_NEW_BOARD_ID=...                     # ULF board ID (where cases get pushed)
TRELLO_NEW_LIST_ID=...                      # Ayush Snipe List ID (or auto-discovered)
WEBSHARE_USERNAME=mryzxzjm                  # your Webshare username prefix
WEBSHARE_PASSWORD=...                       # your Webshare password
WEBSHARE_HOST=p.webshare.io
WEBSHARE_PORT=80
WEBSHARE_SESSION_MIN=2
WEBSHARE_SESSION_MAX=499
PIPELINE_HOST=127.0.0.1
PIPELINE_PORT=8765
PIPELINE_DATA_DIR=./data
PIPELINE_LOG_LEVEL=INFO
PIPELINE_SCHEDULE_CRON=0 20 * * *           # default: daily at 8 PM local time
PIPELINE_LOOKBACK_HOURS=24                  # 24h overlap so missed runs don't lose videos
```

### Getting a Trello token

1. Open this URL in a browser logged into the Trello account that owns the boards:

   `https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&name=interrogation-pipeline&key=<YOUR_KEY>`

   Replace `<YOUR_KEY>` with `TRELLO_API_KEY`.

2. Click **Allow**. The page shows a long token. Paste it as `TRELLO_TOKEN`.

The token never expires (we asked for `expiration=never`). You only need to redo this if you rotate the key.

### Getting your Trello board IDs

If you leave `TRELLO_NEW_BOARD_ID` empty, the pipeline will auto-discover it on first push by name (`ULF`). Same for `TRELLO_NEW_LIST_ID` (`Ayush Snipe List`). For `TRELLO_OLD_BOARD_ID` (`FOIA Trials`), you can leave it empty too — but then the dedup check against your existing 5,650 cards is skipped, and you risk re-adding cases. **Recommended:** look up the IDs once and put them in `.env`.

To find a board ID: open the board in Trello, append `.json` to the URL. The `id` field at the top is what you want. List IDs are inside `lists[]`.

### YouTube cookies

Per pipeline you can have a separate cookies file:

```
backend/data/cookies/cookies_p4.txt   ← required for v1 (P4 channels)
backend/data/cookies/cookies_p1.txt   ← when you turn P1 on
backend/data/cookies/cookies_p3.txt   ← when you turn P3 on
backend/data/cookies/cookies_p2.txt   ← P2 is dormant by default
```

To export: in Chrome, install the "**Get cookies.txt LOCALLY**" extension, log into a throwaway YouTube account, click the extension on `youtube.com`, save the file. Drop it into `backend/data/cookies/` with the right filename.

**Cookies expire every 7-14 days.** When they go stale, the dashboard shows a red banner ("Cookies expired"). Re-export, replace the file, and the next run picks it up.

## Running it

```bash
cd backend
./.venv/bin/python -m interrogation_pipeline       # macOS/Linux
.\.venv\Scripts\python.exe -m interrogation_pipeline   # Windows
```

You'll see something like:

```
INFO  Initializing database…
INFO  Seeded channels: P4=13  P3=4  P1=30  P2=103 (P2 inactive)
INFO  Database ready.
INFO  Scheduler started; cron=0 20 * * *
INFO  Uvicorn running on http://127.0.0.1:8765
```

Open `http://127.0.0.1:8765` in your browser.

The scheduler is now armed. By default it fires daily at **8 PM local time** (so 8 PM IST if your Mac's timezone is IST). Change the cron in Settings → Schedule.

## Using the dashboard

### Today (the page you'll live on)

- **Top stats bar**: P4 coverage — total YT uploads, what we've ingested, % accepted, what's been pushed to Trello.
- **Pipeline picker + Run now**: kick a manual run for any pipeline (P4 default; P1/P2/P3/ALL as choices). Watch the live phase + counts update in real time via Server-Sent Events.
- **Accepted cases**: each is a card with defendant, victim, charges, drama rating, source articles, and three buttons:
  - **Send to Trello**: pushes to ULF → Ayush Snipe List, with last-mile dedup against the cached cards. Disabled if dedup detects this case already exists somewhere.
  - **Mark reviewed**: hides it from Today.
  - **Skip**: same as reviewed.
- **Already on triage / main board** sections: cases that fuzz-matched an existing Trello card. Shown for "peace of mind" but not pushable.
- **Rejected by AI** (collapsed at bottom): every video Haiku said wasn't homicide, with its stated reason. Click to expand. If you spot a mistake, the Override button re-queues it (TBD UI).

### Banners

- **Amber: missing API keys** — fill in `.env` and restart.
- **Red: cookies expired** — re-export `cookies_p4.txt`. Pipeline keeps running for non-cookie work but YouTube scrapes will keep failing until fixed.

### Calendar

Month grid, color-coded by activity. Click a day to see what we found that day.

### Channels

Every channel across all pipelines. Toggle active/inactive (off = won't poll). Move between pipelines via dropdown. Add a new channel by pasting `@handle` or UC ID.

### Runs

Every run ever. Status, duration, counts, and an event log if something errored.

### Settings

- **Schedule cron** — edit + save = scheduler reschedules immediately, no restart needed.
- **Lookback hours** — default 24h. The discovery window's safety margin against missed runs.
- **Concurrency knobs** — how many videos to scrape/scan/verify in parallel.
- **Trello board IDs** — override the auto-discovery.
- **FOIA banned states / agencies** — comma-separated lists. Cases in these locations get a yellow badge but are NOT skipped. Edit + save = takes effect on next case build.

### Stats

- **Anthropic spend** today / 7-day / 30-day / lifetime. Per scan_results.cost_usd.
- **Per-channel coverage** for P4: where each channel stands.

## How it actually works (one paragraph each)

**Discovery** — Once per run, hits each active channel's RSS feed (`https://www.youtube.com/feeds/videos.xml?channel_id=...`). Free, no rate limit. Filters to videos uploaded since `last_seen - 24h` (the lookback overlap is intentional — re-discovery is free because video ID is the primary key). When RSS returns its 15-cap with the oldest still inside the window, falls back to `yt-dlp --flat-playlist` for that one channel to backfill.

**Scrape** — Per video: pick a fresh non-blacklisted Webshare session, run yt-dlp with `--extractor-args 'youtube:player_client=tv'`, `--js-runtimes node`, `--remote-components ejs:github`, `--cookies <file>`. Classifies stderr into typed errors: rate-limited (blacklist + retry), members-only / DRM / no-captions (archive forever), bot-detection (retry up to 5x), cookie-auth-failure (counts toward staleness banner).

**Scan** — Cleaned VTT + title + duration → Claude Haiku 4.5 with the homicide-only prompt. Gets back JSON: rejected (with reason) or accepted (with defendant, victim, charges, drama rating + breakdown, summary). Costs ~$0.007/video.

**Verify** — Per accepted case: Tavily search "<defendant> <victim> murder", returns top 2 articles, sent to Haiku to confirm or correct names ("Carrie Mazooka" → "Keri Mazzuca"). Free if cached. Costs ~$0.005 + $0.005 per accepted case.

**Dedup** — Two layers. Internal dedup within today's accepted cases. External dedup against the Trello card cache (refreshed once per run from both old + new boards). Match rule: defendant ≥85% similar AND 2 of 3 of (victim ≥85%, state exact, year exact). Same as your existing autoloader_v2 logic.

**Push to Trello** — Manual click only. Last-mile dedup re-check against the new board's cache, then create the card with the same description format your VAs are used to.

## Schedule + scheduler quirks

- Cron runs in **local time** (your Mac's TZ).
- The scheduler is a thread inside the FastAPI process. If the process is killed, the cron is dead until you restart.
- "Run now" runs out-of-band; the cron schedule isn't affected.
- If you change the cron in Settings, it reschedules immediately — no restart.
- Verify the next fire time: `GET /api/runs/scheduler/info`.

## Troubleshooting

| Symptom | Probable cause | Fix |
|---|---|---|
| Dashboard says all keys missing | `.env` not loaded | Check the file exists at `backend/.env` and you started the server from the `backend/` dir |
| Scrape archives lots of "DRM protected" | YouTube enrolled this account in their DRM experiment | Switch to a different cookies file / different YT account |
| Scrape archives lots of "no_captions" | Channel has no English auto-captions | Whisper fallback is out of v1 scope; just accept the gap |
| All scrapes fail with "rate limited" | Webshare bandwidth exhausted (HTTP 402) | Top up at https://dashboard.webshare.io |
| Scan stops mid-run with "Anthropic credits exhausted" | Self-explanatory | Top up at https://console.anthropic.com; re-run, scan_progress is preserved |
| "Cookies expired" red banner | 5+ consecutive auth failures on one cookie file | Re-export the file from a logged-in Chrome tab |
| Send to Trello button is disabled | dedup_status != unique (already on a board) | Click the case to see which board it matches; review there instead |
| Calendar shows empty cells | Run hasn't completed yet, or `daily_counts` phase failed | Check Runs → events for the latest run |
| `0 channels checked` in run output | All channels inactive, or pipeline filter excluded all | Channels page → toggle the right ones on |
| n challenge solving failed | yt-dlp can't see your Node install | Verify `node --version` works from the same shell you start the server in |

## Costs at typical volume

For ~100 unique homicide cases per day (which means scanning ~400 transcripts to filter):

- Anthropic Haiku scans: ~$2.80/day
- Tavily verify + Haiku verify on accepted: ~$1.20/day
- Webshare bandwidth: ~$0.04/day (covered by the $27.50/mo residential plan)
- Trello: free
- **Total: ~$120/month** at full volume. Less while channels are catching up.

## Backups

`backend/data/state.db` is the entire system state — channels, runs, scans, cases, Trello cache. Copy that file to back up everything. Re-runs after a crash are free because every state mutation is committed to SQLite.

## Calling for help

If you hit something not in the troubleshooting table, send me:

1. The latest run's events: `curl http://localhost:8765/api/runs/<latest_run_id>/events`
2. The .env (without the secret values)
3. What you tried

— Chaitanya
