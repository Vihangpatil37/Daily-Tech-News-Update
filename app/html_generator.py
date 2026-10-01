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
    active_sources_str: str = "",
    detected_trends: List[str] = None
) -> str:
    """
    Renders the email HTML content using Jinja2 templates.
    """
    templates_dir = BASE_DIR / "templates"
    env = Environment(
        autoescape=select_autoescape(['html', 'xml'])
    )

    template_path = templates_dir / "email.html"
    template_str = template_path.read_text(encoding="utf-8")

    trends_html = ""
    if detected_trends:
        trends_html = '<div class="exec-summary-box" style="margin-top:20px; border-left-color: #f59e0b; background-color: #fffbeb;"><div class="exec-summary-title" style="color: #d97706;">📈 Surging Trends</div><ul style="margin:0; padding-left:20px;">'
        for t in detected_trends:
            trends_html += f'<li style="font-size: 15px; color: #334155;">{t}</li>'
        trends_html += '</ul></div>'
        
    template_str = template_str.replace(
        '<!-- Categorized News Sections -->',
        f'{trends_html}\\n        <!-- Categorized News Sections -->'
    )
    
    deep_dive_template = """
              {{ item.detailed_analysis }}
              {% if item.deep_dive_analysis %}
              <div style="background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 12px; border-radius: 6px; margin-top: 12px; font-size: 13.5px;">
                <h4 style="margin: 0 0 8px 0; color: #334155; display: flex; align-items: center;">🔍 Deep Dive Analysis</h4>
                <p style="margin: 0 0 6px 0;"><strong>Context:</strong> {{ item.deep_dive_analysis.historical_context }}</p>
                <p style="margin: 0 0 6px 0;"><strong>Tech Impact:</strong> {{ item.deep_dive_analysis.technical_impact }}</p>
                <p style="margin: 0 0 6px 0;"><strong>Business:</strong> {{ item.deep_dive_analysis.business_impact }}</p>
                <p style="margin: 0;"><strong>Actionable:</strong> {{ item.deep_dive_analysis.actionable_takeaways }}</p>
              </div>
              {% endif %}
"""
    template_str = template_str.replace('{{ item.detailed_analysis }}', deep_dive_template)

    template = env.from_string(template_str)
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
