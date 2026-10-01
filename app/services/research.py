import asyncio
import httpx
from app.services.llm import _call_gemini_api

async def fetch_hackernews(client: httpx.AsyncClient, topic: str) -> str:
    try:
        url = f"https://hn.algolia.com/api/v1/search?query={topic}"
        response = await client.get(url, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", [])[:5]
        
        results = ["HackerNews Results:"]
        for hit in hits:
            title = hit.get("title") or hit.get("story_title") or "No Title"
            url_ = hit.get("url") or hit.get("story_url") or "No URL"
            results.append(f"- {title} ({url_})")
        return "\n".join(results)
    except Exception as e:
        return f"HackerNews error: {str(e)}"

async def fetch_github(client: httpx.AsyncClient, topic: str) -> str:
    try:
        url = f"https://api.github.com/search/repositories?q={topic}"
        headers = {"User-Agent": "Daily-Tech-News-Update/1.0"}
        response = await client.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])[:5]
        
        results = ["GitHub Results:"]
        for item in items:
            name = item.get("full_name", "No Name")
            desc = item.get("description", "No Description")
            url_ = item.get("html_url", "No URL")
            results.append(f"- {name}: {desc} ({url_})")
        return "\n".join(results)
    except Exception as e:
        return f"GitHub error: {str(e)}"

async def run_deep_research(topic: str) -> str:
    """
    Fetch top context from HackerNews and GitHub concurrently,
    then use Gemini to synthesize a detailed HTML report.
    """
    async with httpx.AsyncClient() as client:
        hn_task = fetch_hackernews(client, topic)
        gh_task = fetch_github(client, topic)
        
        hn_result, gh_result = await asyncio.gather(hn_task, gh_task)
        
    context = f"Topic: {topic}\n\n{hn_result}\n\n{gh_result}"
    
    prompt = (
        f"You are an expert tech analyst. Using the following aggregated search results, "
        f"synthesize a highly detailed, 2-page deep-dive research report on the topic '{topic}'. "
        f"Format the final report as valid, self-contained HTML (using semantic tags like <h1>, <h2>, <p>, <ul>).\n\n"
        f"Context Data:\n{context}\n\n"
        f"Provide only the HTML output. Do not include markdown code block syntax like ```html."
    )
    
    # _call_gemini_api is synchronous and returns (response_text, status_reason)
    response_text, status = _call_gemini_api(prompt)
    if response_text:
        # Strip potential markdown formatting if the LLM returned it anyway
        response_text = response_text.replace("```html", "").replace("```", "").strip()
        return response_text
    else:
        return f"<h1>Error generating report</h1><p>Status: {status}</p>"
