# Paste-into-Claude prompt for Ayush

If you want AI help installing or running this pipeline, open Claude Code (or claude.ai, or any Claude-powered IDE) inside the project root and paste the prompt below as your first message.

This primes Claude with everything it needs to walk you through install + first run + troubleshooting without you re-explaining the project.

---

## 📋 Copy everything in the code block below ⬇

```text
You are helping me set up and run an existing Python + React project called
"Interrogation Pipeline". I cloned it from GitHub. Read these files first to
understand it, then walk me through setup step by step:

  1. README.md             — project overview + quick start
  2. ONBOARDING.md         — full setup + usage instructions
  3. install.sh and install.ps1
  4. backend/.env.example  — environment variables I need to fill in
  5. backend/pyproject.toml + frontend/package.json (just glance)

After reading those, walk me through:

  1. Verify I have the prerequisites:
     - Python 3.11+
     - Node 20+ (REQUIRED — not just for the dashboard build, also for yt-dlp's
       JS challenge solver at runtime; YouTube broke without it)
     - On macOS: ffmpeg via 'brew install ffmpeg' (optional but useful)
  2. Run the right install script for my OS (ask me which).
  3. Help me get my API keys:
     - Anthropic — https://console.anthropic.com (Claude Haiku access)
     - Tavily — https://tavily.com (web search; ~$0.005 per query)
     - Trello key + token — instructions are in ONBOARDING.md "Getting a Trello
       token". The token URL needs my Trello key embedded; help me build it.
     - Webshare residential proxies — https://dashboard.webshare.io
       (use the rotating residential tier; static residential won't work)
  4. Help me find my Trello board IDs:
     - The "old" board for dedup reads (my main FOIA board with thousands of
       existing cards)
     - The "new" board where pipeline cases will be pushed for me to review
     - The list inside the new board where cards land
     If I leave new_board_id and new_list_id empty, the pipeline auto-discovers
     them by name on first push (default names: "ULF" and "Autoload").
     Help me decide what to set.
  5. Help me export YouTube cookies:
     - Install "Get cookies.txt LOCALLY" Chrome extension
     - Log into a throwaway YouTube account in Chrome
     - Click the extension on youtube.com → save cookies
     - Move that file to backend/data/cookies/cookies_p4.txt
     IMPORTANT: cookies expire every 7-14 days; I'll need to re-export
     when the dashboard shows the red "Cookies expired" banner.
  6. Start the server (the one-liner is in ONBOARDING.md).
  7. Open http://localhost:8765 and walk me through what each page does.
  8. Click "Run now" and explain what's happening as it progresses through
     phases (discover → scrape → scan → verify → dedup).

Constraints:
  - Don't modify any code unless I explicitly ask.
  - Don't run any command without telling me what it will do first.
  - If something fails, check ONBOARDING.md "Troubleshooting" first before
     guessing.
  - Don't push API keys, cookies, or anything from backend/data/ to git.
     The .gitignore already covers these but double-check before any
     commit you suggest.

I'm running on: [tell Claude: macOS or Windows]
My experience level: [tell Claude: comfortable with terminal / new to it / etc]

Start by reading the files listed above and then ask me which step I want to
start with.
```

---

## 🧠 Tips when using this with Claude

- **Use Claude Code (the CLI/IDE integration), not just claude.ai chat** — Claude Code can actually read your files, run commands, and verify state. The prompt above assumes that.
- If you only have web claude.ai, paste the contents of `README.md` and `ONBOARDING.md` along with the prompt so Claude has the context.
- When Claude offers to run a command for you, it'll ask permission first — that's normal. Approve only commands that match what you read in the docs.
- If Claude suggests editing code, ask it to explain what's broken first. The pipeline has 58 unit tests; if a test fails after a change, that's the signal to revert.

## ⚠️ Things Claude shouldn't do

- Don't let it commit `.env`, `cookie.txt`, or anything under `backend/data/` to git.
- Don't let it bump dependencies "to fix something" without checking first — yt-dlp + Webshare + YouTube + Anthropic are all moving targets, and the install pins working versions.
- If the dashboard shows red banners (missing keys, stale cookies), those are user actions — Claude can't fix them by editing code.
