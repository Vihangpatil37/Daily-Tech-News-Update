# Tech Intelligence AI Agent

The **Tech Intelligence AI Agent** is an automated, daily batch processing system that collects tech & AI news from 5 major sources, deduplicates & ranks items, summarizes them using the **Google Gemini API**, and delivers a beautifully formatted responsive HTML daily briefing email via **Gmail SMTP**.

---

## 🏗 Architecture & Workflow

```
[ Sources ] ────> [ Deduplication ] ────> [ Pre-Ranking ] ────> [ Gemini LLM ] ────> [ Email HTML ] ────> [ Gmail SMTP ]
 • RSS Feeds       • Cross-source          • Heuristic          • JSON summaries      • Jinja2 render        • Cross-day DB
 • Hacker News     • Rapidfuzz token       • Keyword signal     • Executive briefing  • Critical/High        • Render Cron
 • GitHub Rest       similarity            • Source capping     • Learning advice       color badges         • Seen URLs
 • Dev.to API      • URL domain/slug
 • arXiv API       • 7-day DB filter
```

---

## 🛠 Project Structure

```
tech-agent/
│
├── app/
│   ├── agents/
│   │   ├── __init__.py          # Agent registry
│   │   ├── blog_agent.py        # RSS parser (OpenAI, Anthropic, DeepMind, HuggingFace)
│   │   ├── hackernews_agent.py # HN Firebase API
│   │   ├── github_agent.py     # GitHub REST API (Trending repos + releases)
│   │   ├── devto_agent.py      # Dev.to public API (top tech & programming articles)
│   │   └── arxiv_agent.py      # arXiv API Atom feed parser
│   │
│   ├── services/
│   │   ├── db.py               # SQLite seen_urls deduplication storage
│   │   ├── dedup.py            # Rapidfuzz title similarity & URL deduplication
│   │   ├── ranking.py          # Pre-filter heuristic scoring & source diversity
│   │   ├── llm.py              # Gemini API structured JSON summarizer
│   │   └── gmail.py            # Gmail SMTP SSL delivery layer
│   │
│   ├── models.py               # Data structures (RawItem, ConsolidatedItem, etc.)
│   ├── config.py               # Environment variable validation & config
│   ├── html_generator.py       # Jinja2 template rendering engine
│   ├── orchestrator.py         # End-to-end pipeline runner
│   ├── scheduler_entry.py      # Render Cron Job entrypoint (non-interactive)
│   └── main.py                 # Local / manual execution entrypoint
│
├── templates/
│   └── email.html              # Responsive table-based email template
│
├── data/
│   └── agent.db                # SQLite database (gitignored)
├── logs/
│   └── preview.html            # Rendered dry-run output preview
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

## 🔑 Setup & API Credentials

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Fill in the following credentials:

| Credential | Link to Obtain | Description |
|---|---|---|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) | Free API key for Gemini 2.5 Flash / 1.5 Flash models. |
| `GMAIL_ADDRESS` | Your Gmail address | The sender email address. |
| `GMAIL_APP_PASSWORD` | [Google App Passwords](https://myaccount.google.com/apppasswords) | 16-character app password (requires Gmail 2-Factor Authentication enabled). |
| `RECIPIENT_EMAIL` | Target email address | Destination inbox for the daily report. |
| `GITHUB_TOKEN` | [GitHub Personal Access Tokens](https://github.com/settings/tokens) | Optional. Raises API rate limit from 60/hr to 5,000/hr. |

---

## 🚀 Local Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Dry-Run (Local Preview without sending email)
```bash
python -m app.main --dry-run
```
This generates `logs/preview.html`. Open it in any browser to inspect the email layout!

### 3. Run Full Pipeline (Send Real Email)
```bash
python -m app.main
```

### 4. Run Unit Tests
```bash
pytest
```
or with Python's built-in test runner:
```bash
python -m unittest discover tests
```

---

## ☁️ Deployment on Render

This repository includes a `render.yaml` blueprint configured for **Render Cron Jobs**.

### Render Setup Steps:
1. Push this repository to GitHub or GitLab.
2. Log into [Render Dashboard](https://dashboard.render.com).
3. Click **New +** -> **Blueprint**.
4. Connect your repo. Render will automatically detect `render.yaml`.
5. Under **Environment Variables**, enter values for:
   - `GEMINI_API_KEY`
   - `GMAIL_ADDRESS`
   - `GMAIL_APP_PASSWORD`
   - `RECIPIENT_EMAIL`
   - `GITHUB_TOKEN` (optional)
6. Render will automatically provision persistent disk storage for `data/agent.db` and run `python -m app.scheduler_entry` on schedule (default: `0 2 * * *` = 02:00 UTC / 07:30 AM IST).

---

## ➕ How to Extend (Adding Feeds & Agents)

### Adding a new RSS Feed:
Open `app/agents/blog_agent.py` and add an entry to `RSS_FEEDS`:
```python
{
    "name": "New Tech Blog",
    "urls": ["https://example.com/rss.xml"],
    "category_hint": "Web Development"
}
```

### Adding a new Agent Module:
1. Create a new file in `app/agents/my_agent.py`.
2. Implement the standard interface function:
```python
from typing import List
from app.models import RawItem

def fetch(lookback_hours: int = 24) -> List[RawItem]:
    # Custom fetch logic here...
    return []
```
3. Import and register `my_agent` in `app/agents/__init__.py`:
```python
from . import blog_agent, hackernews_agent, github_agent, devto_agent, arxiv_agent, my_agent

AGENTS = [
    blog_agent,
    hackernews_agent,
    github_agent,
    devto_agent,
    arxiv_agent,
    my_agent
]
```
