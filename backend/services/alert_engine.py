"""
FINN - Alert Trigger Engine
Monitors portfolio EOD price moves, volume anomalies, and material exchange announcements.
Evaluates configurable thresholds and generates prioritized alert feeds.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from database import Company, Price, Announcement, AlertConfig, TriggeredAlert

logger = logging.getLogger(__name__)


def evaluate_eod_alerts(db: Session) -> int:
    """
    Scans the latest EOD prices across all portfolio stocks against user AlertConfig thresholds.
    Generates TriggeredAlert records for any breaches.
    """
    # Fetch active configs
    price_config = db.execute(
        select(AlertConfig).where(AlertConfig.alert_type == "price_move", AlertConfig.enabled == True)
    ).scalar_one_or_none()
    vol_config = db.execute(
        select(AlertConfig).where(AlertConfig.alert_type == "volume_spike", AlertConfig.enabled == True)
    ).scalar_one_or_none()

    price_threshold = price_config.threshold if price_config else 5.0
    vol_threshold = vol_config.threshold if vol_config else 2.0

    companies = db.execute(
        select(Company).where(Company.in_portfolio == True)
    ).scalars().all()

    alerts_created = 0
    now = datetime.utcnow()

    for comp in companies:
        # Get latest price entry
        latest_price = db.execute(
            select(Price)
            .where(Price.company_id == comp.id)
            .order_by(Price.date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if not latest_price:
            continue

        # 1. Price Move Check
        pct_change = latest_price.daily_change_pct
        if pct_change is not None and abs(pct_change) >= price_threshold:
            direction = "surged" if pct_change > 0 else "slumped"
            sign = "+" if pct_change > 0 else ""
            title = f"{comp.ticker} {direction} {sign}{pct_change:.2f}% (Threshold: ±{price_threshold:.1f}%)"
            detail = (
                f"Close: ₹{latest_price.close:,.2f} | Open: ₹{latest_price.open:,.2f} | "
                f"High: ₹{latest_price.high:,.2f} | Low: ₹{latest_price.low:,.2f}."
            )

            # Check if this alert was already triggered for this company today
            existing = db.execute(
                select(TriggeredAlert).where(
                    and_(
                        TriggeredAlert.company_id == comp.id,
                        TriggeredAlert.alert_type == "price_move",
                        TriggeredAlert.title == title,
                    )
                )
            ).scalar_one_or_none()

            if not existing:
                alert = TriggeredAlert(
                    company_id=comp.id,
                    alert_type="price_move",
                    title=title,
                    detail=detail,
                    value=round(pct_change, 2),
                    threshold=price_threshold,
                    severity="HIGH" if abs(pct_change) >= price_threshold * 1.5 else "MEDIUM",
                    triggered_at=now,
                )
                db.add(alert)
                alerts_created += 1

        # 2. Volume Spike Check
        vol_ratio = latest_price.volume_ratio
        if vol_ratio is not None and vol_ratio >= vol_threshold:
            title = f"{comp.ticker} volume spike: {vol_ratio:.1f}x 20-day average"
            detail = (
                f"Traded Volume: {int(latest_price.volume):,} shares. "
                f"Prior 20-day baseline crossed by {((vol_ratio - 1) * 100):.0f}%."
            )

            existing = db.execute(
                select(TriggeredAlert).where(
                    and_(
                        TriggeredAlert.company_id == comp.id,
                        TriggeredAlert.alert_type == "volume_spike",
                        TriggeredAlert.title == title,
                    )
                )
            ).scalar_one_or_none()

            if not existing:
                alert = TriggeredAlert(
                    company_id=comp.id,
                    alert_type="volume_spike",
                    title=title,
                    detail=detail,
                    value=round(vol_ratio, 2),
                    threshold=vol_threshold,
                    severity="HIGH" if vol_ratio >= 3.0 else "MEDIUM",
                    triggered_at=now,
                )
                db.add(alert)
                alerts_created += 1

    db.commit()
    return alerts_created


def evaluate_announcement_alerts(db: Session, hours: int = 48) -> int:
    """
    Evaluates new high-conviction announcements against configured material categories.
    """
    config = db.execute(
        select(AlertConfig).where(AlertConfig.alert_type == "announcement", AlertConfig.enabled == True)
    ).scalar_one_or_none()

    categories_to_watch = config.categories if config and config.categories else [
        "results", "M&A", "management_change", "litigation", "fund_raise"
    ]

    cutoff = datetime.utcnow() - timedelta(hours=hours)

    announcements = db.execute(
        select(Announcement, Company)
        .join(Company)
        .where(
            and_(
                Company.in_portfolio == True,
                Announcement.filed_at >= cutoff,
                Announcement.category.in_(categories_to_watch)
            )
        )
    ).all()

    alerts_created = 0
    for ann, comp in announcements:
        title = f"{comp.ticker} Announcement: {ann.category.upper()}"
        detail = ann.ai_summary or ann.subject

        existing = db.execute(
            select(TriggeredAlert).where(
                and_(
                    TriggeredAlert.company_id == comp.id,
                    TriggeredAlert.alert_type == "announcement",
                    TriggeredAlert.detail == detail,
                )
            )
        ).scalar_one_or_none()

        if not existing:
            alert = TriggeredAlert(
                company_id=comp.id,
                alert_type="announcement",
                title=title,
                detail=detail,
                severity="HIGH" if ann.priority == "HIGH" else "MEDIUM",
                triggered_at=ann.filed_at or datetime.utcnow(),
            )
            db.add(alert)
            alerts_created += 1

    db.commit()
    return alerts_created


def get_active_alerts(db: Session, limit: int = 30) -> List[Dict[str, Any]]:
    """Returns un-dismissed alerts sorted chronologically descending."""
    rows = db.execute(
        select(TriggeredAlert, Company)
        .join(Company)
        .where(TriggeredAlert.dismissed == False)
        .order_by(TriggeredAlert.triggered_at.desc())
        .limit(limit)
    ).all()

    alerts = []
    for alert, comp in rows:
        alerts.append({
            "id": alert.id,
            "company_ticker": comp.ticker,
            "company_name": comp.name,
            "sector": comp.sector,
            "alert_type": alert.alert_type,
            "title": alert.title,
            "detail": alert.detail,
            "value": alert.value,
            "threshold": alert.threshold,
            "severity": alert.severity,
            "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
        })
    return alerts


def dismiss_alert(db: Session, alert_id: int) -> bool:
    """Marks an alert as dismissed."""
    alert = db.execute(
        select(TriggeredAlert).where(TriggeredAlert.id == alert_id)
    ).scalar_one_or_none()

    if alert:
        alert.dismissed = True
        db.commit()
        return True
    return False


def get_alert_configs(db: Session) -> List[Dict[str, Any]]:
    """Fetches user-configurable threshold rules."""
    configs = db.execute(select(AlertConfig)).scalars().all()
    return [
        {
            "id": c.id,
            "alert_type": c.alert_type,
            "threshold": c.threshold,
            "direction": c.direction,
            "categories": c.categories,
            "enabled": c.enabled,
        }
        for c in configs
    ]


def update_alert_config(db: Session, config_id: int, threshold: float = None, enabled: bool = None) -> Optional[Dict[str, Any]]:
    """Updates user threshold settings."""
    cfg = db.execute(select(AlertConfig).where(AlertConfig.id == config_id)).scalar_one_or_none()
    if not cfg:
        return None

    if threshold is not None:
        cfg.threshold = threshold
    if enabled is not None:
        cfg.enabled = enabled

    db.commit()
    return {
        "id": cfg.id,
        "alert_type": cfg.alert_type,
        "threshold": cfg.threshold,
        "enabled": cfg.enabled,
    }

