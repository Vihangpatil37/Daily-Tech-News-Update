# Tech Intelligence AI Agent — Implementation Prompt (MVP → Full Spec)

This document is a **ready-to-paste prompt** for an AI coding agent (Claude Code, Cursor, etc.)
to scaffold and build the Tech Intelligence AI Agent described in
`Tech_Intelligence_AI_Agent_Project_Specification.md`. It locks in the architecture decisions
we made, scopes an MVP that ships fast, and lays out a clear path back to the full 17-category
vision.

---

## 1. Locked-In Architecture Decisions

| Decision | Choice | Why |
|---|---|---|
| LLM (summarization + ranking) | **Google Gemini API** (`gemini-flash-latest` alias, currently resolving to Gemini 3.5 Flash) | Cheap, fast, generous free tier — good fit for a daily batch job. Check `https://ai.google.dev/gemini-api/docs/models` before deploying, since Google rotates model IDs. |
| Initial scope | **MVP with 5 sources**, then expand | The full spec has 17 categories and dozens of sources — building all of it at once is a multi-month project. Ship something that lands in an inbox first. |
| Hosting / execution | **Render** (Python Background Worker + Render Cron Job) | Netlify Functions only support JS/TS/Go — no Python. Render supports Python natively, has built-in scheduled jobs, and a managed Postgres upgrade path. |
| Future dashboard | **Netlify (or Vercel)**, static/JS front-end only, reading from the same DB | Matches the "Web dashboard" item already in the spec's Future Enhancements. Doesn't touch the Python pipeline. |
| Email delivery | **SMTP + Gmail App Password** (`smtplib`) | Full Gmail API OAuth2 is more robust but requires a consent screen, token refresh handling, etc. App Password is a 5-minute setup and is fine for a single-recipient personal agent. |
| Storage | **SQLite** (file on Render persistent disk) for MVP → **Postgres** (Render managed) in Phase 2 | Needed to remember what's already been sent (cross-day dedup) and to eventually support semantic search / weekly reports. SQLite is zero-config for MVP. |

---

## 2. MVP Scope

### Sources included (Phase 1)
1. **Official AI blogs via RSS** — OpenAI, Anthropic, Google DeepMind (add more feeds later)
2. **Hacker News** — top stories + AI/tech-tagged stories (via the free Firebase HN API)
3. **GitHub Trending** — trending repos + notable releases (via GitHub REST API)
4. **Reddit** — r/MachineLearning, r/programming (via Reddit's OAuth API)
5. **arXiv** — recent AI/ML papers (via the arXiv API)

### Spec categories covered by the MVP
- Artificial Intelligence (via blogs, HN)
- Large Language Models (via blogs, HN, arXiv)
- GitHub Trending (dedicated)
- AI Research (via arXiv)
- General developer buzz (via HN, Reddit)

### Deferred to Phase 2 (see §8 Roadmap)
Programming Languages, Web Development, Technology Companies, Cloud, Cybersecurity,
Developer Tools, Mobile Development, Game Engines, YouTube, Podcasts, Engineering Blogs,
Jobs.

### Email structure for MVP
Keep the full target structure from the spec, but categories with no MVP source simply don't
render that day (don't show empty sections). This keeps the email structure future-proof —
Phase 2 sources slot into existing template blocks.

---

## 3. Folder Structure

```
tech-agent/
│
├── app/
│   ├── agents/
│   │   ├── blog_agent.py        # RSS: OpenAI/Anthropic/DeepMind blogs
│   │   ├── hackernews_agent.py
│   │   ├── github_agent.py
│   │   ├── reddit_agent.py
│   │   └── arxiv_agent.py
│   │
│   ├── services/
│   │   ├── gmail.py              # SMTP send
│   │   ├── llm.py                # Gemini calls (summarize, classify, rank)
│   │   ├── dedup.py              # cross-source + cross-day deduplication
│   │   ├── ranking.py            # heuristic pre-filter + importance scoring
│   │   └── db.py                 # SQLite access layer
│   │
│   ├── scheduler_entry.py        # entrypoint Render Cron Job calls
│   ├── orchestrator.py           # runs the full pipeline end to end
│   ├── html_generator.py         # renders templates/email.html via Jinja2
│   ├── config.py                 # env var loading + validation
│   └── main.py                   # local/manual run entrypoint
│
├── templates/
│   └── email.html
│
├── data/
│   └── agent.db                  # SQLite file (gitignored, lives on Render disk)
├── logs/
├── tests/
│   ├── test_dedup.py
│   ├── test_ranking.py
│   └── test_agents.py
├── requirements.txt
├── render.yaml
├── .env.example
└── README.md
```

---

## 4. Environment Variables / Secrets

```
# LLM
GEMINI_API_KEY=

# Sources
GITHUB_TOKEN=              # optional but recommended (raises rate limit from 60/hr to 5000/hr)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=tech-intel-agent/0.1 by <your-reddit-username>

# Email
GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=        # generate at https://myaccount.google.com/apppasswords
RECIPIENT_EMAIL=

# Misc
DATABASE_PATH=data/agent.db
TIMEZONE=Asia/Kolkata       # used only for display/date formatting in the email
LOOKBACK_HOURS=24
```

---

## 5. The Implementation Prompt

> Paste everything in this section to your coding agent as the task description.

```
Build a Python 3.11 project called "tech-agent" that sends a daily HTML "Tech Intelligence
Daily" email to Gmail, summarizing the last 24 hours of AI/tech news. Follow this exact
folder structure: [paste Section 3 folder structure]. Use Section 4's environment variables,
loaded via python-dotenv locally and Render's env var UI in production.

PIPELINE (app/orchestrator.py orchestrates all of this, called by app/scheduler_entry.py):

1. COLLECTION
   Each agent in app/agents/ implements a common interface:
       def fetch(lookback_hours: int) -> list[RawItem]
   where RawItem is a dataclass: {title, url, source, published_at, raw_summary,
   engagement_score (upvotes/stars/points, 0 if unavailable), category_hint}.
   - blog_agent.py: use `feedparser` against a configurable list of RSS URLs
     (start with OpenAI's blog, Anthropic's blog, Google DeepMind's blog — resolve current
     feed URLs, don't hardcode guesses; verify each feed actually parses).
   - hackernews_agent.py: use the free Firebase HN API
     (https://hacker-news.firebaseio.com/v0/) — pull /topstories.json, fetch item details,
     filter to items within lookback_hours, keep score as engagement_score.
   - github_agent.py: use the GitHub REST API's search/repositories endpoint sorted by
     stars, filtered to `created:>{date}` for trending-in-last-day repos, plus check
     releases for a short watchlist of major AI repos. Use GITHUB_TOKEN if present.
   - reddit_agent.py: use Reddit's OAuth "script" app flow (client credentials grant) to
     hit /r/MachineLearning/top and /r/programming/top with t=day. Store upvotes as
     engagement_score.
   - arxiv_agent.py: use the arXiv API (http://export.arxiv.org/api/query) filtered to
     cs.AI/cs.CL/cs.LG categories, sorted by submission date.
   Every agent must catch and log its own exceptions and return an empty list on failure —
   one broken source must never crash the whole run.

2. DEDUPLICATION (app/services/dedup.py)
   - Normalize titles (lowercase, strip punctuation).
   - Use rapidfuzz's token_sort_ratio to cluster items whose titles are >85% similar OR
     whose URLs share the same domain+slug.
   - When a cluster has multiple items, merge them into one ConsolidatedItem that keeps
     the highest engagement_score, lists all contributing sources, and picks the earliest
     published_at.
   - Cross-day dedup: before clustering, check app/services/db.py's `seen_urls` table and
     drop any URL already sent in the last 7 days.

3. RANKING (app/services/ranking.py)
   - Compute a cheap heuristic pre-score per ConsolidatedItem: weight by engagement_score
     (normalized per source), number of merged sources (more sources = more important),
     and keyword matches against a configurable HIGH_SIGNAL_KEYWORDS list (e.g. "release",
     "launch", "GA", "acquisition", "breach", "CVE", plus the company/product names from
     the spec's tracked lists).
   - Take the top ~25 items overall (cap per category to avoid one category dominating)
     and pass ONLY those to the LLM stage — don't burn LLM calls ranking obviously minor
     items.

4. LLM SUMMARIZATION (app/services/llm.py)
   - Call the Gemini API once per shortlisted item (or batch a handful per call if you can
     keep the JSON response schema reliable — test both, prefer whichever is more robust).
   - System prompt must instruct Gemini to return strict JSON:
       {
         "headline": str,          # <=12 words
         "summary": str,           # 2-3 sentences, what happened
         "why_it_matters": str,    # 1-2 sentences
         "developer_impact": str,  # does a developer need to act/migrate/learn something
         "importance": "Critical" | "High" | "Medium" | "Low",
         "category": one of the 17 spec categories
       }
   - Validate the JSON; on parse failure, retry once, then skip the item and log it rather
     than crashing the run.
   - After all items are summarized, make ONE final Gemini call that takes the day's
     headlines and returns: executive_summary (counts + 2-3 sentence overview) and
     learning_recommendation ({topic, reason, resources: [str]}).

5. HTML GENERATION (app/html_generator.py)
   - Use Jinja2 to render templates/email.html against: date, executive_summary, items
     grouped by category (only non-empty categories), learning_recommendation, and an
     estimated_reading_time computed from total word count / 200wpm.
   - Template must be responsive (inline CSS, table-based layout is safest for Gmail
     rendering), match the structure in the spec's "Target Email Structure" section, and
     visually distinguish Critical/High/Medium/Low items (e.g. a colored left border or
     badge).

6. DELIVERY (app/services/gmail.py)
   - Use smtplib + ssl over smtp.gmail.com:465, authenticating with GMAIL_ADDRESS and
     GMAIL_APP_PASSWORD, sending a multipart MIME email (HTML body) to RECIPIENT_EMAIL.
   - On successful send, record all included URLs into the `seen_urls` table with today's
     date, so tomorrow's cross-day dedup works.

7. ENTRYPOINTS
   - app/main.py: run the full pipeline once, synchronously, with verbose logging — for
     local testing without needing a real cron trigger.
   - app/scheduler_entry.py: same as main.py but tuned for a non-interactive Render Cron
     Job run (log to logs/, exit with non-zero code on unhandled failure so Render flags
     the job as failed).

8. CONFIG & VALIDATION (app/config.py)
   - Load all Section 4 env vars via python-dotenv locally / os.environ in production.
   - On startup, validate that all required vars are present and fail fast with a clear
     error listing exactly which ones are missing.

9. TESTS
   - Unit test dedup clustering logic with synthetic near-duplicate titles.
   - Unit test the ranking heuristic's ordering with synthetic engagement scores.
   - Mock each agent's HTTP calls (use `responses` or `unittest.mock`) so tests run without
     network access or real API keys.

10. README.md must include:
    - Setup steps for every API credential (Gemini key, GitHub token, Reddit app
      client id/secret, Gmail App Password) with links to where to generate each one.
    - Local run instructions (`python -m app.main`).
    - Render deployment instructions matching render.yaml.
    - How to add a new RSS feed or a new agent module (since Phase 2 will add many).

Non-negotiables:
- No source failure should ever crash the whole run — always degrade gracefully and log.
- Never call the LLM on the full raw item set — always pre-filter first (cost control).
- Keep agent interfaces identical across all five agents so adding a sixth is a copy-paste.
- All secrets via environment variables only — never hardcoded, never committed.
```

---

## 6. Render Deployment Notes

`render.yaml` (Background Worker + Cron Job):

```yaml
services:
  - type: cron
    name: tech-agent-daily
    env: python
    schedule: "0 2 * * *"   # 02:00 UTC = 07:30 AM IST — adjust to taste
    buildCommand: pip install -r requirements.txt
    startCommand: python -m app.scheduler_entry
    envVars:
      - key: GEMINI_API_KEY
        sync: false
      - key: GITHUB_TOKEN
        sync: false
      - key: REDDIT_CLIENT_ID
        sync: false
      - key: REDDIT_CLIENT_SECRET
        sync: false
      - key: GMAIL_ADDRESS
        sync: false
      - key: GMAIL_APP_PASSWORD
        sync: false
      - key: RECIPIENT_EMAIL
        sync: false
    disk:
      name: agent-data
      mountPath: /opt/render/project/data
      sizeGB: 1
```

Mark all secret env vars `sync: false` so they're set once in the Render dashboard, not
committed to the repo.

---

## 7. Testing & Validation Checklist

- [ ] Each agent runs standalone and returns items (`python -m app.agents.hackernews_agent`)
- [ ] Killing network access to one source doesn't break a full pipeline run
- [ ] Dedup correctly merges a story that appears on both HN and a company blog
- [ ] LLM JSON output validates against the schema on 20+ consecutive real items
- [ ] Email renders correctly in actual Gmail (not just a browser preview — table layouts
      can break in Gmail's clipped CSS support)
- [ ] Cross-day dedup: running the pipeline twice in one day sends nothing the second time
- [ ] Render Cron Job fires at the scheduled time and the email arrives

---

## 8. Phase 2 Roadmap

Once the MVP is stable for a week or two:

1. **Expand sources** to cover the remaining spec categories: official engineering blogs
   (Cloudflare, Netflix Tech, AWS, etc.), YouTube Data API for channel uploads, cloud
   provider changelogs (AWS/Azure/GCP), CVE feeds (NVD API) for cybersecurity, dev tool
   changelogs (VS Code, Cursor, Docker).
2. **Move SQLite → Postgres** (Render managed) once you want cross-week trend queries or
   multiple recipients.
3. **Semantic dedup/clustering** — replace the rapidfuzz heuristic with Gemini embeddings
   for more accurate cross-source clustering.
4. **Web dashboard** — a small Netlify or Vercel static site (or Next.js app) reading from
   Postgres, giving a searchable archive of past briefings.
5. **Multi-channel delivery** — Slack/Telegram/Discord webhook alongside email.
6. **Weekly/monthly rollups** — a second, less-frequent Render Cron Job that queries the
   history table for trend analysis.

---

*Source spec: `Tech_Intelligence_AI_Agent_Project_Specification.md`. Architecture choices
above were confirmed interactively: Gemini for LLM, MVP-first scope with 5 sources, Render
for execution (Netlify not viable for Python), SMTP + Gmail App Password for delivery.*
