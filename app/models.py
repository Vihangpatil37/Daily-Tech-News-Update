from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class RawItem(BaseModel):
    """Represents a single raw news item retrieved from a source agent."""
    title: str
    url: str
    source: str
    published_at: str
    raw_summary: str
    engagement_score: float = 0.0
    category_hint: Optional[str] = None

class ConsolidatedItem(BaseModel):
    """Represents a merged item resulting from deduplication across sources."""
    id: str
    title: str
    url: str
    sources: List[str]
    published_at: str
    raw_summary: str
    engagement_score: float = 0.0
    category_hint: Optional[str] = None
    pre_score: float = 0.0

class ProcessedItem(BaseModel):
    """Represents an item processed and summarized by the LLM."""
    headline: str
    summary: str
    detailed_analysis: str
    why_it_matters: str
    developer_impact: str
    importance: str  # "Critical", "High", "Medium", or "Low"
    category: str
    url: str
    sources: List[str]
    published_at: str
    engagement_score: float = 0.0
    deep_dive_analysis: Optional[dict] = None

class DailyBriefing(BaseModel):
    """Complete summary data for rendering the HTML email."""
    date_str: str
    executive_summary: str
    items_by_category: Dict[str, List[ProcessedItem]]
    learning_recommendation: Dict[str, Any]  # {"topic": str, "reason": str, "resources": List[str]}
    estimated_reading_time: int  # in minutes
    total_items_analyzed: int
    detected_trends: List[str] = []
