"""
FINN - Price & Volume Fetcher (yfinance EOD)
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from database import Company, Price
from config import PRICE_HISTORY_PERIOD

logger = logging.getLogger(__name__)


def fetch_prices_for_company(
    db: Session,
    company: Company,
    period: str = PRICE_HISTORY_PERIOD,
    force: bool = False,
) -> int:
    """
    Fetch EOD prices for a single company from yfinance and store in DB.
    Returns number of new rows inserted.
    """
    ticker_obj = yf.Ticker(company.yf_ticker)

    # Check latest date in DB to avoid re-fetching
    if not force:
        latest = db.execute(
            select(func.max(Price.date)).where(Price.company_id == company.id)
        ).scalar()
        if latest and (datetime.utcnow() - latest).days < 1:
            logger.info(f"[{company.ticker}] Prices up to date, skipping")
            return 0

    try:
        hist = ticker_obj.history(period=period, interval="1d")
    except Exception as e:
        logger.error(f"[{company.ticker}] yfinance error: {e}")
        return 0

    if hist.empty:
        logger.warning(f"[{company.ticker}] No price data returned")
        return 0

    # Compute derived signals
    hist["daily_change_pct"] = hist["Close"].pct_change() * 100
    hist["vol_20d_avg"] = hist["Volume"].rolling(20).mean()
    hist["volume_ratio"] = hist["Volume"] / hist["vol_20d_avg"]
    hist["volatility_20d"] = hist["Close"].pct_change().rolling(20).std() * 100

    inserted = 0
    for date_idx, row in hist.iterrows():
        dt = date_idx.to_pydatetime().replace(tzinfo=None)
        # Skip if already exists
        exists = db.execute(
            select(Price).where(
                Price.company_id == company.id,
                Price.date == dt
            )
        ).scalar_one_or_none()
        if exists:
            continue

        price = Price(
            company_id=company.id,
            date=dt,
            open=float(row.get("Open", 0)),
            high=float(row.get("High", 0)),
            low=float(row.get("Low", 0)),
            close=float(row.get("Close", 0)),
            volume=float(row.get("Volume", 0)),
            adj_close=float(row.get("Close", 0)),
            daily_change_pct=float(row.get("daily_change_pct", 0)) if pd.notna(row.get("daily_change_pct")) else None,
            volume_ratio=float(row.get("volume_ratio", 0)) if pd.notna(row.get("volume_ratio")) else None,
            volatility_20d=float(row.get("volatility_20d", 0)) if pd.notna(row.get("volatility_20d")) else None,
        )
        db.add(price)
        inserted += 1

    db.commit()
    logger.info(f"[{company.ticker}] Inserted {inserted} price rows")
    return inserted


def fetch_all_portfolio_prices(db: Session, force: bool = False) -> dict:
    """Fetch prices for all portfolio companies."""
    companies = db.execute(
        select(Company).where(Company.in_portfolio == True)
    ).scalars().all()

    results = {}
    for company in companies:
        try:
            count = fetch_prices_for_company(db, company, force=force)
            results[company.ticker] = {"status": "ok", "rows": count}
        except Exception as e:
            results[company.ticker] = {"status": "error", "error": str(e)}
            logger.error(f"[{company.ticker}] Failed: {e}")

    return results


def get_latest_prices(db: Session) -> list[dict]:
    """Get the most recent price for each portfolio company."""
    companies = db.execute(
        select(Company).where(Company.in_portfolio == True)
    ).scalars().all()

    result = []
    for company in companies:
        latest = db.execute(
            select(Price)
            .where(Price.company_id == company.id)
            .order_by(Price.date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if latest:
            result.append({
                "ticker": company.ticker,
                "name": company.name,
                "sector": company.sector,
                "close": latest.close,
                "daily_change_pct": latest.daily_change_pct,
                "volume": latest.volume,
                "volume_ratio": latest.volume_ratio,
                "date": latest.date.isoformat() if latest.date else None,
            })

    return result


def get_price_history(db: Session, ticker: str, days: int = 180) -> list[dict]:
    """Get price history for a specific company."""
    company = db.execute(
        select(Company).where(Company.ticker == ticker)
    ).scalar_one_or_none()

    if not company:
        return []

    cutoff = datetime.utcnow() - timedelta(days=days)
    prices = db.execute(
        select(Price)
        .where(Price.company_id == company.id, Price.date >= cutoff)
        .order_by(Price.date.asc())
    ).scalars().all()

    return [
        {
            "date": p.date.isoformat(),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
            "volume": p.volume,
            "daily_change_pct": p.daily_change_pct,
            "volume_ratio": p.volume_ratio,
        }
        for p in prices
    ]
