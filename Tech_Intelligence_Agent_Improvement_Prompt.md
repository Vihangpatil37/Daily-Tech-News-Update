# Tech Intelligence AI Agent — Improvement Prompt (Reddit Swap + Reliability + Quality Fixes)

This is a **ready-to-paste prompt** for a coding agent (Claude Code, Cursor, etc.) to apply a
focused round of fixes to the existing `tech-agent` project. It was written after auditing the
codebase (`app/agents/`, `app/services/llm.py`, `app/services/ranking.py`,
`templates/email.html`) against a real sent email (`Tech Intelligence Daily — July 23, 2026`).

---

## 1. Diagnosis — what's actually wrong

| Symptom in the email | Root cause | File |
|---|---|---|
| "Reddit" listed as a source but zero Reddit items ever appear | `reddit_agent.py` falls back to Reddit's **unauthenticated** JSON endpoint when no OAuth token is configured. Reddit blocks most cloud/datacenter IPs from that endpoint (HTTP 403), so it silently returns nothing most runs. | `app/agents/reddit_agent.py` |
| Several items show boilerplate text — *"Why It Matters: Relevant update from top tech sources."* / *"Developer Impact: Review source details for technical specifications."* — including the "Deep Dive" recommendation itself | This is a **hardcoded fallback** in `llm.py` that fires whenever the Gemini call fails or its JSON can't be parsed. The pipeline makes **one Gemini API call per shortlisted item** (up to 25/run) plus one final call, with no throttling and no rate-limit-specific backoff — it almost certainly hits Gemini's free-tier RPM limit partway through each run, so later items (and the final summary call) fall back to the generic strings. | `app/services/llm.py` |
| GitHub Trending section is full of low-signal, single-digit/low-star repos, all tagged "MEDIUM" | `github_agent.py` has **no minimum star threshold** — it takes the top 30 repos created in the last 2 days sorted by stars, with no floor, so brand-new repos with a handful of stars get in. `ranking.py`'s `max_per_source=6` then lets up to 6 of them through per run. | `app/agents/github_agent.py`, `app/services/ranking.py` |
| Header reads "Analyzed 46 sources" | This is mislabeled — `total_items_analyzed` is actually the **raw item count** (articles/posts/repos pulled before dedup), not a count of sources. The project only has ~7 source integrations. | `app/html_generator.py`, `templates/email.html` (line ~200) |
| Footer hardcodes "Sources: OpenAI, Anthropic, DeepMind, Hacker News, GitHub Trending, Reddit, arXiv" | Static string that doesn't reflect which agents actually ran or returned data that day — it will still say "Reddit" even after Reddit is removed unless someone remembers to edit the template. | `templates/email.html` (line ~268) |

---

## 2. Decisions locked for this round

| Decision | Choice | Why |
|---|---|---|
| Reddit replacement | **Dev.to (Forem) public API** | Free, **no auth required** for reads (the exact problem Reddit had), well-documented, tag-filterable, returns real engagement signals (`positive_reactions_count`, `comments_count`). Covers the same ground the two subreddits did: `r/MachineLearning` → AI-tagged articles, `r/programming` → programming/webdev-tagged articles. |
| Rate-limit fix strategy | **Batch + throttle + real backoff**, not just a bigger retry count | Cheapest fix that also cuts Gemini call volume ~4-5x, which is the actual lever that prevents rate-limiting rather than just retrying into the same wall. |
| GitHub Trending quality | **Minimum star threshold + tighter per-source cap** | Keeps the section meaningful without needing a new data source. |
| Source-count label | **Rename + make dynamic** | Fixes the misleading "sources" label and stops the footer from silently lying about which sources ran. |

---

## 3. The Implementation Prompt

> Paste everything in this section to your coding agent as the task description. It assumes the
> agent has access to the existing `tech-agent` repo.

```
Apply the following changes to the existing "tech-agent" Python project. Do not restructure
anything not mentioned below. After each change, run the existing test suite
(`python -m pytest`) and fix anything it breaks.

────────────────────────────────────────
1. REMOVE REDDIT, ADD DEV.TO
────────────────────────────────────────
- Delete app/agents/reddit_agent.py.
- Remove REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT from app/config.py,
  .env / .env.example, README.md's setup instructions, and render.yaml's envVars list.
- Create app/agents/devto_agent.py implementing the same fetch(lookback_hours) -> list[RawItem]
  interface as the other agents. Use the public Forem/DEV API
  (https://developers.forem.com/api/v0 — verify current field names against the live docs,
  don't hardcode guesses):
    - No API key required for public reads, but send a real User-Agent header.
    - Query GET https://dev.to/api/articles with tag + top params, e.g.:
        tag=machinelearning, top=1  -> category_hint="Artificial Intelligence"
        tag=ai, top=1               -> category_hint="Artificial Intelligence"
        tag=programming, top=1      -> category_hint="General Developer Buzz"
        tag=webdev, top=1           -> category_hint="Web Development"
      ("top=1" returns the top articles from roughly the last day — confirm the exact window
      semantics against current docs and adjust to match lookback_hours as closely as possible.)
    - Map each article to RawItem: title -> title, url -> url (use the article's canonical
      url field), source="Dev.to", published_at -> published_at/published_timestamp,
      raw_summary -> description (or body_markdown truncated to ~500 chars if description is
      empty), engagement_score -> positive_reactions_count (or public_reactions_count,
      whichever the live schema uses) + (comments_count * 2), category_hint as above.
    - Deduplicate articles that match multiple tag queries before returning.
    - Catch and log all exceptions; return an empty list on failure, exactly like the other
      agents — one broken source must never crash the run.
- Update app/agents/__init__.py: replace reddit_agent with devto_agent in the AGENTS list.
- Update templates/email.html footer and any other hardcoded "Reddit" mentions (see #4 below —
  make this list dynamic instead of hand-editing it).
- Add a standalone test block at the bottom of devto_agent.py (mirroring reddit_agent.py's
  `if __name__ == "__main__":` block) so it can be run directly:
  `python -m app.agents.devto_agent`.

────────────────────────────────────────
2. FIX THE LLM RATE-LIMITING / GENERIC-FALLBACK ROOT CAUSE
────────────────────────────────────────
In app/services/llm.py:
- Add a module-level throttle: track the timestamp of the last Gemini call and sleep as needed
  before the next call so requests stay comfortably under Gemini's current free-tier RPM limit
  for the model in use (check https://ai.google.dev/gemini-api/docs/rate-limits for the current
  number — don't hardcode last year's limit — and pick a safe interval with margin, not the
  exact ceiling).
- Detect HTTP 429 / rate-limit errors specifically (both from the google-genai SDK exception
  and the REST fallback's status code) and distinguish them in logs from JSON-parse failures or
  missing-API-key cases — right now all three collapse into one generic warning, which is why
  this bug was invisible in the logs.
- On a detected 429, apply real exponential backoff (e.g. wait 15s, then 30s) before the retry,
  instead of immediately retrying or falling through to the heuristic fallback.
- Batch multiple shortlisted items into a single Gemini call instead of one call per item:
  send an array of items in the prompt and request a JSON array of results matching the
  existing per-item schema, in the same order as the input. Aim for batches of ~5 items. This
  cuts a 25-item run from ~26 Gemini calls down to ~6, which is the main lever that prevents
  hitting the rate limit in the first place. Validate the returned array length matches the
  input batch length; if it doesn't, or JSON parsing fails, fall back to per-item calls for just
  that batch rather than failing the whole batch silently.
- Keep the existing heuristic fallback (ProcessedItem with generic why_it_matters/
  developer_impact) as the last resort when both the batched and per-item calls fail — but log
  it at WARNING with the specific reason (rate_limited / parse_error / no_api_key) so failures
  are diagnosable from logs going forward.

────────────────────────────────────────
3. IMPROVE GITHUB TRENDING QUALITY
────────────────────────────────────────
In app/agents/github_agent.py:
- Add a minimum star threshold (e.g. MIN_STARS = 50, exposed as a constant near the top of the
  file so it's easy to tune) and skip repos below it in the "recently created trending repos"
  search block. Releases from WATCHLIST_REPOS are exempt (they're curated, not filtered by
  stars).
In app/services/ranking.py:
- Lower max_per_source specifically for the "GitHub Trending" source (e.g. cap it at 3 instead
  of the shared max_per_source=6), so the category is a highlight reel, not a dump of every repo
  that cleared the (now-higher) star bar. Keep max_per_source=6 as the default for other
  sources unless told otherwise.

────────────────────────────────────────
4. FIX THE "SOURCES ANALYZED" LABEL AND FOOTER
────────────────────────────────────────
- In app/html_generator.py / app/orchestrator.py: rename the concept currently called
  total_items_analyzed in the template context so the email is honest about what it's counting.
  Either:
    (a) relabel the badge text in templates/email.html from "Analyzed {{ total_items_analyzed }}
        sources" to "Analyzed {{ total_items_analyzed }} articles across {{ active_source_count
        }} sources", passing a new active_source_count computed as the number of distinct
        agent modules that returned at least one item that run, OR
    (b) simpler alternative: just change the word "sources" to "items" in that badge.
  Prefer (a) if it's a small change; fall back to (b) if it adds meaningful complexity.
- Replace the hardcoded footer line ("Sources: OpenAI, Anthropic, DeepMind, Hacker News,
  GitHub Trending, Reddit, arXiv") with a dynamically generated list built from which agents
  in app.agents.AGENTS actually returned >0 items that run, passed into the template context.
  This prevents this exact bug (a stale/inaccurate source list) from recurring the next time a
  source is added or removed.

────────────────────────────────────────
5. TESTS
────────────────────────────────────────
- Add tests/test_devto_agent.py (or extend tests/test_agents.py) mocking the Dev.to API
  response and asserting RawItem mapping is correct, matching the style of existing agent tests.
- Add a unit test for llm.py's batching: mock a Gemini response containing a JSON array and
  assert it's correctly split back into per-item ProcessedItem objects in order.
- Add a unit test for the new GitHub star-threshold filter.
- Update/remove any existing reddit_agent tests.

Non-negotiables (same as the original build):
- No source failure should ever crash the whole run — always degrade gracefully and log.
- All secrets via environment variables only — never hardcoded, never committed.
- Keep every agent's interface identical (fetch(lookback_hours) -> list[RawItem]) so agents
  stay swappable.
```

---

## 4. Environment variable changes

```diff
- REDDIT_CLIENT_ID=
- REDDIT_CLIENT_SECRET=
- REDDIT_USER_AGENT=tech-intel-agent/0.1 by <your-reddit-username>
```

No new environment variables are required — Dev.to's read endpoints don't need an API key.
(Optional: `DEVTO_API_KEY` could be added later only if you start hitting Dev.to's unauthenticated
rate limit, which is generous for a once-a-day batch job.)

---

## 5. Validation checklist

- [ ] `python -m app.agents.devto_agent` runs standalone and returns real articles
- [ ] Full pipeline run (`python -m app.main --dry-run` or equivalent) with network access to
      only Dev.to's domain still succeeds (no crash from the removed Reddit agent)
- [ ] A forced-low rate-limit test (or manual log inspection) confirms batched Gemini calls per
      run drop from ~26 to ~6 and that 429s are now logged distinctly and retried with backoff
- [ ] A test run shows zero "Relevant update from top tech sources." fallback strings under
      normal conditions
- [ ] GitHub Trending section in a real run shows ≤3 items, all above the new star threshold
- [ ] Header badge and footer source list in a rendered email both reflect reality (no more
      "Reddit" if it returned nothing that day; item vs. source count no longer conflated)
- [ ] `python -m pytest` passes, including new/updated tests

---

*This prompt is a follow-up to `Tech_Intelligence_AI_Agent_Implementation_Prompt.md`. All
findings above were confirmed by reading the actual source files
(`reddit_agent.py`, `llm.py`, `github_agent.py`, `ranking.py`, `html_generator.py`,
`templates/email.html`) rather than assumed from the email output alone.*
