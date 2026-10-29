"""
FINN - Digest Engine (Push)
Generates windowed digests of announcements for the portfolio.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from database import Announcement, Company
from config import PRIORITY_MAP, CHEAP_MODEL
from services.model_router import call_llm
from services.announcement_classifier import classify_announcement, enrich_announcement

logger = logging.getLogger(__name__)


def generate_digest(
    db: Session,
    hours: int = 24,
    ticker: Optional[str] = None,
) -> dict:
    """
    Generate a prioritized digest of announcements within the time window.
    
    Returns:
    {
        "window": "24h",
        "generated_at": "...",
        "summary": "...",      # AI overview
        "total": 12,
        "high": [...],
        "medium": [...],
        "low": [...],
        "skipped": 3,
    }
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    query = (
        select(Announcement, Company)
        .join(Company)
        .where(Announcement.filed_at >= cutoff)
    )
    if ticker:
        query = query.where(Company.ticker == ticker)

    query = query.order_by(Announcement.filed_at.desc())
    rows = db.execute(query).all()

    # Classify any unclassified announcements
    for ann, comp in rows:
        if not ann.category:
            try:
                classify_announcement(db, ann)
            except Exception as e:
                logger.error(f"Classification failed: {e}")
                ann.category = "unclassified"
                ann.priority = "SKIP"
                db.commit()

    # Enrich HIGH priority items
    for ann, comp in rows:
        if ann.priority == "HIGH" and not ann.enrichment:
            try:
                enrich_announcement(db, ann)
            except Exception as e:
                logger.error(f"Enrichment failed: {e}")

    # Group by priority
    high, medium, low, skipped = [], [], [], 0
    for ann, comp in rows:
        item = _format_announcement(ann, comp)
        if ann.priority == "HIGH":
            high.append(item)
        elif ann.priority == "MEDIUM":
            medium.append(item)
        elif ann.priority == "LOW":
            low.append(item)
        else:
            skipped += 1

    # Generate overview summary if there are HIGH items
    overview = ""
    if high:
        overview = _generate_overview(db, high, hours)

    return {
        "window": f"{hours}h",
        "generated_at": datetime.utcnow().isoformat(),
        "summary": overview,
        "total": len(rows),
        "high": high,
        "medium": medium,
        "low": low,
        "skipped": skipped,
    }


def _format_announcement(ann: Announcement, comp: Company) -> dict:
    return {
        "id": ann.id,
        "ticker": comp.ticker,
        "company_name": comp.name,
        "sector": comp.sector,
        "filed_at": ann.filed_at.isoformat() if ann.filed_at else None,
        "subject": ann.subject,
        "category": ann.category,
        "priority": ann.priority,
        "ai_summary": ann.ai_summary,
        "enrichment": ann.enrichment,
        "attachment_url": ann.attachment_url,
    }


def _generate_overview(db: Session, high_items: list[dict], hours: int) -> str:
    """Generate a brief overview of the most important items."""
    items_text = "\n".join([
        f"- [{item['ticker']}] {item['category']}: {item['ai_summary'] or item['subject']}"
        for item in high_items[:10]
    ])

    prompt = f"""In the last {hours} hours, these material events occurred across the portfolio:

{items_text}

Write a 2-3 sentence executive summary for an investor, highlighting the most important developments. Be direct and specific."""

    return call_llm(
        prompt=prompt,
        system="You are a concise financial briefing writer. No fluff, no disclaimers.",
        model=CHEAP_MODEL,
        task_name="digest_overview",
        db=db,
    )
