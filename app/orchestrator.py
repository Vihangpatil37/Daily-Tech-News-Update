import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

from app.config import LOOKBACK_HOURS, TIMEZONE, BASE_DIR
from app.models import RawItem, ConsolidatedItem, ProcessedItem
from app.agents import AGENTS
from app.services import db, dedup, ranking, llm, gmail
from app import html_generator

logger = logging.getLogger("tech-agent.orchestrator")


def run_pipeline(lookback_hours: int = None, dry_run: bool = False, recipient_override: str = None) -> bool:
    """
    Executes the complete Tech Intelligence AI Agent pipeline end-to-end.
    """
    hours = lookback_hours if lookback_hours is not None else LOOKBACK_HOURS
    logger.info("==================================================")
    logger.info("Starting Tech Intelligence Pipeline (Lookback=%dh, DryRun=%s)", hours, dry_run)
    logger.info("==================================================")

    # 1. Initialize Database
    db.init_db()

    # 2. Collection Stage
    all_raw_items: List[RawItem] = []
    active_sources_set = set()

    for agent in AGENTS:
        agent_name = agent.__name__.split('.')[-1]
        try:
            items = agent.fetch(lookback_hours=hours)
            if items:
                all_raw_items.extend(items)
                for item in items:
                    if item.source:
                        active_sources_set.add(item.source)
                logger.info("Agent %s returned %d items.", agent_name, len(items))
            else:
                logger.info("Agent %s returned 0 items.", agent_name)
        except Exception as e:
            logger.error("Unexpected error running agent %s: %s", agent_name, e)

    total_raw_count = len(all_raw_items)
    active_sources_list = sorted(list(active_sources_set))
    active_source_count = len(active_sources_list)
    active_sources_str = ", ".join(active_sources_list) if active_sources_list else "None"

    logger.info("Collection complete. Total raw items gathered: %d across %d active sources (%s)",
                total_raw_count, active_source_count, active_sources_str)

    if not all_raw_items:
        logger.warning("No items collected from any source. Pipeline stopping early.")
        return False

    # 3. Deduplication Stage
    consolidated_items = dedup.deduplicate(all_raw_items, enable_cross_day=True, lookback_days=7)
    if not consolidated_items:
        logger.info("No new items after deduplication. Nothing to send today.")
        return True

    # 4. Ranking & Shortlisting Stage
    shortlisted = ranking.rank_and_shortlist(consolidated_items, max_total=25)
    if not shortlisted:
        logger.info("No items passed pre-filter shortlist.")
        return True

    # 5. LLM Summarization Stage (Batched)
    processed_items = llm.batch_summarize_items(shortlisted, batch_size=5)

    if not processed_items:
        logger.warning("No items were successfully processed by LLM/fallback.")
        return False

    # Group by category
    items_by_category: Dict[str, List[ProcessedItem]] = defaultdict(list)
    for p_item in processed_items:
        items_by_category[p_item.category].append(p_item)

    # 6. Executive Summary & Meta Generation
    meta = llm.generate_daily_briefing_meta(processed_items)
    exec_summary = meta.get("executive_summary", "")
    learning_rec = meta.get("learning_recommendation", {})

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # 7. HTML Rendering
    html_content = html_generator.render_email_html(
        date_str=date_str,
        executive_summary=exec_summary,
        items_by_category=dict(items_by_category),
        learning_recommendation=learning_rec,
        total_items_analyzed=total_raw_count,
        active_source_count=active_source_count,
        active_sources_str=active_sources_str
    )

    sent_urls_and_titles: List[Tuple[str, str]] = [(item.url, item.headline) for item in processed_items]

    # 8. Delivery or Preview
    if dry_run:
        preview_dir = BASE_DIR / "logs"
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / "preview.html"
        preview_path.write_text(html_content, encoding="utf-8")
        logger.info("DRY RUN: Saved email preview HTML to %s", preview_path)
        print(f"\n[DRY RUN COMPLETE] Preview rendered to: {preview_path}\n")
        return True
    else:
        subject = f"Tech Intelligence Daily — {date_str}"
        success = gmail.send_email(
            subject=subject,
            html_content=html_content,
            sent_urls_and_titles=sent_urls_and_titles,
            recipient_override=recipient_override
        )
        if not success:
            # Fallback save to preview.html if email delivery fails
            preview_dir = BASE_DIR / "logs"
            preview_dir.mkdir(parents=True, exist_ok=True)
            preview_path = preview_dir / "failed_send_preview.html"
            preview_path.write_text(html_content, encoding="utf-8")
            logger.warning("Email delivery failed. Saved HTML to %s", preview_path)
        return success
