# Hey Ayush — here's what I'm building for you

Look bro, I went through your whole handoff doc, the recording, the prompt PDF, the channels sheet — the works. Wanted to lay out exactly what I'm putting together for you in plain English before I start writing code, so we're on the same page and you can tell me if anything's off.

## TL;DR

A daily web dashboard you open in your browser. It checks your snipe channels every day, finds murder cases worth FOIA-ing, dedupes against your existing Trello board, and shows everything (including what the AI rejected) in one screen. You click "Send to Trello" on the ones you want pushed — they go into a NEW Trello board, not your main one. Nothing auto-adds anywhere without you saying so.

## What this fixes for you

You said it best in the recording — you can't manually watch hundreds of videos a week, and your current setup is half-built and Mac-locked. Here's what changes:

1. **You stop missing videos.** Right now if your Mac is asleep or your terminal crashes mid-run, you lose visibility. New system has a 24h lookback window plus a weekly safety-net job. A video uploaded at 11pm IST? Caught. A run failed yesterday? Caught next run.
2. **No more "did the AI miss something?" anxiety.** The dashboard shows the rejected videos at the bottom of the page with the AI's stated reason. One click to override if you spot a mistake.
3. **Cross-platform.** Runs on Mac or Windows. No more `caffeinate -s`, no more launchd, no more ~/Desktop hardcoded paths.
4. **Real visibility.** Calendar view to scroll back through any day. Stats panel showing "we found 1,847 of 2,008 videos posted on P4 channels". You can actually see what the system is doing.
5. **Your main Trello board stays clean.** Nothing auto-pushes there. New cases land in a separate "triage" board. You promote the ones you want with a click.

## How it works (one paragraph)

Every day at the time you set, a Python program wakes up, hits each P4 channel's YouTube RSS feed (free, unauthenticated, no rate-limit), finds new videos, downloads only the new ones' captions through your Webshare proxies, sends each transcript to Claude Haiku with the homicide-only prompt you gave me, runs Tavily on the accepted ones to fix misspelled names, dedupes against BOTH your existing main Trello board AND the new triage board, then drops everything into the dashboard for you to review. You open localhost:8765, see today's results, click through, push what you like to Trello.

## What you'll see in the browser

**Today's page** — the main view:
- Top: a stats bar — "P4 coverage: 1,847 of 2,008 videos (92%) — 612 cases accepted — 487 in Trello"
- Middle: today's accepted cases as cards. Each shows defendant, victim, charges, drama rating, video link, AI summary. Buttons: **Send to Trello**, **Skip**, **Mark reviewed**.
- Bottom (collapsed by default): rejected cases with the AI's stated rejection reason. Click any one to expand the transcript and override if the AI got it wrong.
- A red banner at the top if anything's broken — Anthropic credits out, Webshare bandwidth gone, cookies stale, etc.

**Calendar page** — month view, color-coded by activity. Click any day to see exactly what the system found that day. Failed days highlighted red.

**Channels page** — every channel with its YT total, our coverage, last seen time. Toggle a channel on/off. Move it between pipelines (P1/P2/P3/P4) with a dropdown. Add a new channel by pasting its URL.

**Runs page** — every daily run with status, duration, error breakdown. Click for the full event log if something went sideways.

**Settings page** — schedule (default 24h, can do 12h or any cron), the lookback buffer (24h default — the timezone fix you asked about), API key health checks, Trello board IDs, proxy session range.

**Stats page** — costs this week, AI override rate (so we can tell if the prompt needs tuning), per-channel coverage breakdown.

## The timezone thing you flagged

You mentioned a video uploaded at 11pm IST sometimes lands on the "wrong" day. Fixed:
- Everything internal is UTC. Frontend formats to IST for display only.
- Discovery uses a 24h lookback (configurable to 48h or whatever you want). So even if a daily run runs late or skips, the next run still sees yesterday's late-night uploads. Re-seeing a video is free because we dedup by YouTube video ID.
- A separate weekly reconciliation job sweeps each channel's full video list to catch anything RSS lagged on. Triple-redundant — a video can't fall through.

## What I'm building under the hood (in case you care)

- **Backend**: Python 3.12, FastAPI, APScheduler for the daily timer, SQLite for state (one file, you can back it up by copying it), SQLAlchemy ORM. Async — uses `httpx` for everything that hits the network.
- **Frontend**: React + Vite. Built once into static files that the same Python process serves. After install, you don't need Node running — only Python.
- **Reusing your proven logic**: per-video proxy rotation with 30-min blacklist on rate-limit, the `tv` player_client + `--no-check-certificates` flag set, your multi-field fuzzy dedup (defendant ≥85% + 2 of 3 of victim/state/year), the homicide-only prompt from Prompt.pdf with the additive drama rubric.
- **Discovery is RSS first, yt-dlp second**: RSS finds new video IDs daily (free, no rate-limit, no proxy). yt-dlp + your residential proxy only downloads captions for those specific new IDs. Bandwidth use drops dramatically vs your current "scan all videos" pattern.

## Scope for v1 (what ships first)

**P4 only** (your 13 snipe channels). That's the priority you stated. Once it's stable and proven for a week or two, P1 (your 30 new interrogation channels) is a config change — no code changes.

P2 stays dormant. P3 has the DRM problem on `@LawAndCrimeInvestigates` and we agreed Whisper is out of scope, so P3 is deferred.

## What I'm NOT building (so there are no surprises)

- No Whisper transcription (you said skip).
- No email/Slack alerts (the dashboard banner does this job for v1; we can add later).
- No multi-user / login / auth — it's localhost-only by default.
- No mobile app.

## What I need from you

When you're ready:
1. **Anthropic API key** (claude-haiku access)
2. **Tavily API key**
3. **Webshare credentials** (just confirming the residential rotating tier and the username — `mryzxzjm` per the handoff)
4. **Trello key + token + the OLD board ID** (your main `FOIA Trials` board — for dedup reads)
5. **Trello NEW board** — either you create a board named whatever you want and send me its ID + the target list ID, OR tell me to create one programmatically on first run. Either works.
6. **Cookie file** — your `cookies_p4.txt` exported from a logged-in YouTube account in Chrome (or I'll send instructions if you want a fresh one).

## Timeline reality check

You mentioned "tomorrow night" at the end of the recording. Honest answer: with the React frontend, that's tight. I can probably get you a working **backend + a basic dashboard** in 24 hours that does the full pipeline and lets you push to Trello — but the calendar view, stats page, and polish will take another day or two. Want me to ship in that order? (Functional first, pretty after.)

## What "done" looks like

- One command: `python -m interrogation_pipeline` starts everything.
- Browser to `localhost:8765`. Dashboard loads. You click "Run now". Watch the live progress.
- New cases appear. You review. Push the good ones to your new Trello board.
- Tomorrow it does it again on its own.

That's the whole thing, bro. Tell me what to change before I start writing code.

— Chaitanya
