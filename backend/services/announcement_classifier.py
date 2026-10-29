"""
FINN - Announcement Classifier
Uses LLM to classify announcements into 17 categories and generate summaries.
"""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from database import Announcement, Company
from config import ANNOUNCEMENT_CATEGORIES, PRIORITY_MAP, CHEAP_MODEL
from services.model_router import call_llm

logger = logging.getLogger(__name__)

CLASSIFY_SYSTEM = """You are a financial analyst classifying Indian stock exchange corporate announcements.
Given an announcement subject and description, classify it into EXACTLY ONE of these categories:

results, M&A, fund_raise, management_change, litigation, insider_trading, earnings_call, 
investor_meetings, credit_rating, dividend, bonus_split, capex, press_release, 
postal_ballot, agm_egm, pledging, unclassified

Also provide a concise 1-2 sentence summary that tells an investor what matters.

Respond in JSON format:
{"category": "...", "summary": "..."}
"""

ENRICH_RESULTS_SYSTEM = """You are a financial analyst. Given quarterly results filing text, extract these headline numbers:
- Revenue (total income / net sales)
- EBITDA
- PBT (Profit Before Tax)  
- PAT (Profit After Tax / Net Profit)

For each, provide the current quarter value and compute QoQ (vs previous quarter) and YoY (vs same quarter last year) change percentages IF that data is available in the text.

Respond in JSON:
{
  "revenue": {"value": ..., "unit": "Cr", "qoq_pct": ..., "yoy_pct": ...},
  "ebitda": {"value": ..., "unit": "Cr", "qoq_pct": ..., "yoy_pct": ...},
  "pbt": {"value": ..., "unit": "Cr", "qoq_pct": ..., "yoy_pct": ...},
  "pat": {"value": ..., "unit": "Cr", "qoq_pct": ..., "yoy_pct": ...}
}

If a value is not available, use null. All amounts in Crores (Cr).
"""

ENRICH_MGMT_SYSTEM = """You are a business researcher. Given a management change announcement, extract:
1. The person's name
2. Their role (CEO, CFO, MD, Director, etc.)
3. Whether they are joining, resigning, or retiring
4. A brief professional background (2-3 lines) based on what's in the announcement

Respond in JSON:
{
  "person_name": "...",
  "role": "...", 
  "action": "joining|resigning|retiring",
  "background": "..."
}
"""


def classify_announcement(
    db: Session, 
    announcement: Announcement,
) -> dict:
    """
    Classify a single announcement using cheap LLM.
    Updates the announcement record in DB with category, priority, and summary.
    """
    if announcement.category and announcement.ai_summary:
        return {
            "category": announcement.category,
            "priority": announcement.priority,
            "summary": announcement.ai_summary,
        }

    text = f"Subject: {announcement.subject}\n"
    if announcement.description:
        text += f"Description: {announcement.description[:1000]}"

    result = call_llm(
        prompt=text,
        system=CLASSIFY_SYSTEM,
        model=CHEAP_MODEL,
        task_name="classify_announcement",
        json_mode=True,
        db=db,
    )

    try:
        parsed = json.loads(result)
        category = parsed.get("category", "unclassified")
        if category not in ANNOUNCEMENT_CATEGORIES:
            category = "unclassified"
        summary = parsed.get("summary", "")
    except (json.JSONDecodeError, TypeError):
        category = "unclassified"
        summary = result[:200] if result else ""

    priority = PRIORITY_MAP.get(category, "SKIP")

    # Update DB
    announcement.category = category
    announcement.priority = priority
    announcement.ai_summary = summary
    db.commit()

    return {"category": category, "priority": priority, "summary": summary}


def classify_all_unclassified(db: Session) -> int:
    """Classify all announcements that haven't been classified yet."""
    unclassified = db.execute(
        select(Announcement).where(Announcement.category == None)
    ).scalars().all()

    count = 0
    for ann in unclassified:
        try:
            classify_announcement(db, ann)
            count += 1
        except Exception as e:
            logger.error(f"Classification failed for ann #{ann.id}: {e}")

    return count


def enrich_results_announcement(
    db: Session,
    announcement: Announcement,
) -> Optional[dict]:
    """
    For results announcements: extract Revenue, EBITDA, PBT, PAT with QoQ/YoY.
    """
    if announcement.category != "results":
        return None

    text = f"Company filing:\nSubject: {announcement.subject}\n"
    if announcement.description:
        text += f"Content: {announcement.description[:3000]}"

    result = call_llm(
        prompt=text,
        system=ENRICH_RESULTS_SYSTEM,
        model=CHEAP_MODEL,
        task_name="enrich_results",
        json_mode=True,
        db=db,
    )

    try:
        parsed = json.loads(result)
        announcement.enrichment = parsed
        db.commit()
        return parsed
    except (json.JSONDecodeError, TypeError):
        return None


def enrich_management_change(
    db: Session,
    announcement: Announcement,
) -> Optional[dict]:
    """
    For management change announcements: extract person bio.
    """
    if announcement.category != "management_change":
        return None

    text = f"Management change announcement:\nSubject: {announcement.subject}\n"
    if announcement.description:
        text += f"Content: {announcement.description[:2000]}"

    result = call_llm(
        prompt=text,
        system=ENRICH_MGMT_SYSTEM,
        model=CHEAP_MODEL,
        task_name="enrich_mgmt_change",
        json_mode=True,
        db=db,
    )

    try:
        parsed = json.loads(result)
        announcement.enrichment = parsed
        db.commit()
        return parsed
    except (json.JSONDecodeError, TypeError):
        return None


def enrich_announcement(db: Session, announcement: Announcement) -> Optional[dict]:
    """Route to the right enrichment function based on category."""
    if announcement.enrichment:
        return announcement.enrichment

    if announcement.category == "results":
        return enrich_results_announcement(db, announcement)
    elif announcement.category == "management_change":
        return enrich_management_change(db, announcement)

    return None
