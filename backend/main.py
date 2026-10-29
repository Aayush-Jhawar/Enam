"""
FINN - Financial Investment Agent API
FastAPI backend providing institutional-grade Push (Windowed Digest, Alert Engine)
and Pull (Primary Grounded Fundamental Research Suite & Any-Ticker Analyzer).
"""
import logging
import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from database import init_db, get_db, Company, Price, Announcement, DocumentChunk, TriggeredAlert, AlertConfig
from services.digest_engine import generate_digest
from services.alert_engine import (
    get_active_alerts, dismiss_alert, get_alert_configs,
    update_alert_config, evaluate_eod_alerts, evaluate_announcement_alerts
)
from services.research_engine import ResearchEngine
from services.price_fetcher import get_latest_prices, fetch_all_portfolio_prices
from services.model_router import get_total_cost

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finn.api")

app = FastAPI(
    title="FINN - Financial Investment Agent API",
    description="Primary-source grounded equity intelligence layer built for ENAM Holdings.",
    version="1.0.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("FINN API initialized successfully.")


# ── Health & Diagnostics ────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    comp_count = db.query(Company).count()
    price_count = db.query(Price).count()
    ann_count = db.query(Announcement).count()
    chunk_count = db.query(DocumentChunk).count()
    alert_count = db.query(TriggeredAlert).filter(TriggeredAlert.dismissed == False).count()

    return {
        "status": "operational",
        "agent": "FINN (ENAM Holdings Build Challenge)",
        "database": {
            "companies": comp_count,
            "prices_recorded": price_count,
            "announcements": ann_count,
            "primary_document_chunks": chunk_count,
            "active_alerts": alert_count,
        }
    }


# ── Watchlist & Companies ───────────────────────────────────────────────────

@app.get("/api/companies", tags=["Portfolio"])
def list_companies(in_portfolio: Optional[bool] = None, db: Session = Depends(get_db)):
    """Returns tracked companies along with their most recent EOD closing metrics."""
    stmt = select(Company)
    if in_portfolio is not None:
        stmt = stmt.where(Company.in_portfolio == in_portfolio)
    companies = db.execute(stmt).scalars().all()

    results = []
    for comp in companies:
        latest_price = db.execute(
            select(Price).where(Price.company_id == comp.id).order_by(Price.date.desc()).limit(1)
        ).scalar_one_or_none()

        results.append({
            "ticker": comp.ticker,
            "name": comp.name,
            "sector": comp.sector,
            "in_portfolio": comp.in_portfolio,
            "market_cap_category": comp.market_cap_category,
            "close": latest_price.close if latest_price else None,
            "daily_change_pct": latest_price.daily_change_pct if latest_price else None,
            "volume_ratio": latest_price.volume_ratio if latest_price else None,
        })
    return results


# ── PUSH MODE: Windowed Digest & Triggered Alerts ───────────────────────────

@app.get("/api/push/digest", tags=["Push Mode"])
def get_digest(
    hours: int = Query(24, ge=1, le=720, description="Window in hours (e.g. 24, 48, 168)"),
    ticker: Optional[str] = Query(None, description="Optional single ticker filter"),
    db: Session = Depends(get_db)
):
    """
    Returns prioritized windowed digest across the portfolio.
    Surfaces HIGH priority events with AI summaries and structured extractions,
    collapses routine administrative paperwork.
    """
    return generate_digest(db, hours=hours, ticker=ticker)


@app.get("/api/push/alerts", tags=["Push Mode"])
def get_alerts(limit: int = 30, db: Session = Depends(get_db)):
    """Surfaces active threshold-triggered alerts (unusual volume, price swings, material filings)."""
    return get_active_alerts(db, limit=limit)


@app.post("/api/push/alerts/{alert_id}/dismiss", tags=["Push Mode"])
def dismiss_triggered_alert(alert_id: int, db: Session = Depends(get_db)):
    """Dismisses an active alert from the notification feed."""
    success = dismiss_alert(db, alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "dismissed", "alert_id": alert_id}


@app.get("/api/push/alert-configs", tags=["Push Mode"])
def list_alert_configs(db: Session = Depends(get_db)):
    """Returns configurable threshold rules for price swings, volume anomalies, and filings."""
    return get_alert_configs(db)


class AlertConfigUpdate(BaseModel):
    threshold: Optional[float] = None
    enabled: Optional[bool] = None


@app.put("/api/push/alert-configs/{config_id}", tags=["Push Mode"])
def modify_alert_config(config_id: int, payload: AlertConfigUpdate, db: Session = Depends(get_db)):
    """Updates user-defined alert thresholds."""
    updated = update_alert_config(db, config_id, threshold=payload.threshold, enabled=payload.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert configuration not found")
    return updated


@app.post("/api/push/refresh", tags=["Push Mode"])
def refresh_market_eod(db: Session = Depends(get_db)):
    """Runs on-demand evaluation of price moves and announcement alerts."""
    p_alerts = evaluate_eod_alerts(db)
    a_alerts = evaluate_announcement_alerts(db, hours=48)
    return {
        "status": "evaluated",
        "new_price_alerts": p_alerts,
        "new_announcement_alerts": a_alerts,
    }


# ── PULL MODE: Deep Primary Research Engine ─────────────────────────────────

@app.get("/api/pull/research/{ticker}", tags=["Pull Mode"])
def get_company_research(
    ticker: str,
    module: Optional[str] = Query(None, description="One of: business_snapshot, financial_snapshot, trajectory, balance_sheet, cash_quality, narrative_vs_numbers, guidance, bull_vs_bear"),
    db: Session = Depends(get_db)
):
    """
    On-demand institutional research grounded exclusively in primary documents (Annual Reports + Concalls).
    Works on ANY NSE ticker.
    """
    engine = ResearchEngine(db)
    try:
        report = engine.analyze_company(ticker, module=module)
        return report
    except Exception as e:
        logger.error(f"Error researching {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pull/index/{ticker}", tags=["Pull Mode"])
def index_external_company(ticker: str, db: Session = Depends(get_db)):
    """Indexes primary document chunks for any ad-hoc or newly queried NSE stock."""
    from services.fundamentals_fetcher import build_index_for_company
    clean_ticker = ticker.upper().replace(".NS", "").replace(".BO", "")
    result = build_index_for_company(db, clean_ticker, max_docs=2)
    return result


# ── Audit & Cost Tracking ───────────────────────────────────────────────────

@app.get("/api/audit/costs", tags=["Audit"])
def audit_compute_costs(db: Session = Depends(get_db)):
    """Returns detailed compute expenditure audit, demonstrating smart model routing efficiency."""
    return get_total_cost(db)


# ── Mount Frontend Static Web Application ───────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
