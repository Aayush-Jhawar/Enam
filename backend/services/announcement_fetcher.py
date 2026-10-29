"""
FINN - Corporate Announcement Fetcher (NSE/BSE)
Scrapes announcements from NSE API and RSS feed, stores in DB.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import feedparser
import requests
from sqlalchemy.orm import Session
from sqlalchemy import select

from database import Company, Announcement
from config import NSE_BASE_URL, NSE_API_ANNOUNCEMENTS, NSE_RSS_URL

logger = logging.getLogger(__name__)

# ── NSE Session Management ──────────────────────────────────────────────────

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
    "Connection": "keep-alive",
}


def _get_nse_session() -> requests.Session:
    """Create a session with valid NSE cookies."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        # Hit homepage to get cookies
        session.get(NSE_BASE_URL, timeout=10)
        time.sleep(1)
    except Exception as e:
        logger.warning(f"NSE session init failed: {e}")
    return session


# ── Fetch from NSE JSON API ─────────────────────────────────────────────────

def fetch_nse_announcements_for_symbol(
    session: requests.Session,
    symbol: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict]:
    """
    Fetch corporate announcements for a specific NSE symbol.
    Returns list of raw announcement dicts.
    """
    params = {"index": "equities", "symbol": symbol}
    if from_date:
        params["from_date"] = from_date  # DD-MM-YYYY
    if to_date:
        params["to_date"] = to_date

    try:
        resp = session.get(NSE_API_ANNOUNCEMENTS, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, list) else []
        else:
            logger.warning(f"NSE API returned {resp.status_code} for {symbol}")
            return []
    except Exception as e:
        logger.error(f"NSE API error for {symbol}: {e}")
        return []


# ── Fetch from NSE RSS Feed (fallback) ──────────────────────────────────────

def fetch_nse_rss_announcements() -> list[dict]:
    """
    Fallback: fetch latest announcements from NSE RSS feed.
    Returns normalized list.
    """
    try:
        feed = feedparser.parse(NSE_RSS_URL)
        results = []
        for entry in feed.entries[:100]:
            results.append({
                "symbol": _extract_symbol_from_rss(entry),
                "subject": entry.get("title", ""),
                "description": entry.get("summary", ""),
                "filed_at": _parse_rss_date(entry.get("published", "")),
                "attachment_url": entry.get("link", ""),
                "source": "NSE_RSS",
            })
        return results
    except Exception as e:
        logger.error(f"NSE RSS fetch failed: {e}")
        return []


def _extract_symbol_from_rss(entry: dict) -> str:
    """Try to extract company symbol from RSS entry title."""
    title = entry.get("title", "")
    # NSE RSS titles often start with the symbol
    parts = title.split(" - ", 1)
    if len(parts) > 1:
        return parts[0].strip().upper()
    return ""


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse RSS date format."""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()


# ── Store announcements ─────────────────────────────────────────────────────

def store_announcements(db: Session, company: Company, raw_list: list[dict]) -> int:
    """
    Store raw announcements in DB. Returns count of new rows.
    Deduplicates by subject + filed_at.
    """
    inserted = 0
    for raw in raw_list:
        subject = raw.get("desc", raw.get("subject", raw.get("smDesc", "")))
        filed_str = raw.get("an_dt", raw.get("dt", raw.get("filed_at", "")))

        if isinstance(filed_str, str):
            filed_at = _parse_announcement_date(filed_str)
        elif isinstance(filed_str, datetime):
            filed_at = filed_str
        else:
            filed_at = datetime.utcnow()

        attach_url = raw.get("attchmntFile", raw.get("attachment_url", ""))
        if attach_url and not attach_url.startswith("http"):
            attach_url = f"https://nsearchives.nseindia.com/corporate/Attachments/{attach_url}"

        # Dedup check
        exists = db.execute(
            select(Announcement).where(
                Announcement.company_id == company.id,
                Announcement.subject == subject[:500] if subject else "",
                Announcement.filed_at == filed_at,
            )
        ).scalar_one_or_none()

        if exists:
            continue

        ann = Announcement(
            company_id=company.id,
            source=raw.get("source", "NSE"),
            filed_at=filed_at,
            subject=subject[:500] if subject else "",
            description=raw.get("attchmntText", raw.get("description", "")),
            attachment_url=attach_url,
        )
        db.add(ann)
        inserted += 1

    db.commit()
    return inserted


def _parse_announcement_date(date_str: str) -> datetime:
    """Parse various date formats from NSE."""
    formats = [
        "%d-%b-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d %b %Y",
        "%d-%b-%Y",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return datetime.utcnow()


# ── Main fetch pipeline ────────────────────────────────────────────────────

def fetch_all_portfolio_announcements(
    db: Session,
    days_back: int = 30,
) -> dict:
    """Fetch announcements for all portfolio companies."""
    companies = db.execute(
        select(Company).where(Company.in_portfolio == True)
    ).scalars().all()

    session = _get_nse_session()
    from_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%m-%Y")
    to_date = datetime.now().strftime("%d-%m-%Y")

    results = {}
    for company in companies:
        try:
            raw = fetch_nse_announcements_for_symbol(
                session, company.ticker, from_date, to_date
            )
            if not raw:
                # Fallback to RSS
                logger.info(f"[{company.ticker}] NSE API empty, trying RSS...")
                rss_all = fetch_nse_rss_announcements()
                raw = [a for a in rss_all if a.get("symbol") == company.ticker]

            count = store_announcements(db, company, raw)
            results[company.ticker] = {"status": "ok", "new": count, "total_fetched": len(raw)}
            time.sleep(2)  # Rate limiting
        except Exception as e:
            results[company.ticker] = {"status": "error", "error": str(e)}
            logger.error(f"[{company.ticker}] Announcement fetch failed: {e}")

    return results


def get_announcements(
    db: Session,
    hours: int = 24,
    ticker: Optional[str] = None,
) -> list[dict]:
    """Get announcements within a time window, optionally for a specific ticker."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    query = select(Announcement, Company).join(Company).where(
        Announcement.filed_at >= cutoff
    )
    if ticker:
        query = query.where(Company.ticker == ticker)

    query = query.order_by(Announcement.filed_at.desc())
    rows = db.execute(query).all()

    return [
        {
            "id": ann.id,
            "ticker": comp.ticker,
            "company_name": comp.name,
            "filed_at": ann.filed_at.isoformat() if ann.filed_at else None,
            "subject": ann.subject,
            "description": ann.description,
            "category": ann.category,
            "priority": ann.priority,
            "ai_summary": ann.ai_summary,
            "enrichment": ann.enrichment,
            "attachment_url": ann.attachment_url,
        }
        for ann, comp in rows
    ]
