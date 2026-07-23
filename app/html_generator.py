import logging
from pathlib import Path
from typing import Dict, List, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.config import BASE_DIR
from app.models import ProcessedItem

logger = logging.getLogger("tech-agent.html")


def compute_reading_time(items_by_category: Dict[str, List[ProcessedItem]], executive_summary: str) -> int:
    """Computes estimated reading time in minutes based on total word count (200 wpm)."""
    word_count = len(executive_summary.split())
    for items in items_by_category.values():
        for item in items:
            word_count += len(item.headline.split())
            word_count += len(item.summary.split())
            word_count += len(item.why_it_matters.split())
            word_count += len(item.developer_impact.split())

    minutes = max(1, round(word_count / 200))
    return minutes


def render_email_html(
    date_str: str,
    executive_summary: str,
    items_by_category: Dict[str, List[ProcessedItem]],
    learning_recommendation: Dict[str, Any],
    total_items_analyzed: int,
    active_source_count: int = 0,
    active_sources_str: str = ""
) -> str:
    """
    Renders the email HTML content using Jinja2 templates.
    """
    templates_dir = BASE_DIR / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(['html', 'xml'])
    )

    template = env.get_template("email.html")
    reading_time = compute_reading_time(items_by_category, executive_summary)

    html_content = template.render(
        date_str=date_str,
        executive_summary=executive_summary,
        items_by_category=items_by_category,
        learning_recommendation=learning_recommendation,
        estimated_reading_time=reading_time,
        total_items_analyzed=total_items_analyzed,
        active_source_count=active_source_count,
        active_sources_str=active_sources_str or "Tech Intelligence Sources"
    )

    logger.info("Successfully rendered email HTML (%d characters, est. %d min read).", len(html_content), reading_time)
    return html_content
