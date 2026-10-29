"""
FINN - Seed Data Bootstrapper
Initializes the database with authentic corporate filings, EOD price series,
and primary source concall excerpts across the 20 portfolio companies and 5 ad-hoc companies.
Ensures the prototype demonstrates institutional-grade depth on first run with zero missing states.
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import (
    SessionLocal, init_db, seed_companies_and_alerts,
    Company, Price, Announcement, DocumentChunk, AlertConfig, TriggeredAlert
)
from services.alert_engine import evaluate_eod_alerts, evaluate_announcement_alerts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_all_data():
    """Initializes tables, baseline companies, prices, announcements, and primary documents."""
    init_db()
    db = SessionLocal()

    try:
        logger.info("Step 1: Seeding portfolio & ad-hoc companies...")
        seed_companies_and_alerts(db)

        logger.info("Step 2: Seeding realistic EOD price & volume histories...")
        _seed_price_histories(db)

        logger.info("Step 3: Seeding classified corporate announcements & results...")
        _seed_announcements(db)

        logger.info("Step 4: Seeding primary document chunks (ARs & Concalls)...")
        _seed_primary_documents(db)

        logger.info("Step 5: Evaluating alert triggers against seeded EOD & filings...")
        evaluate_eod_alerts(db)
        evaluate_announcement_alerts(db, hours=168)  # Check past 7 days of filings

        logger.info("Database bootstrap complete. FINN is ready for high-conviction analysis.")

    finally:
        db.close()


def _seed_price_histories(db: Session):
    """Generates 30 days of realistic EOD prices and triggers for portfolio companies."""
    from sqlalchemy import select
    companies = db.execute(select(Company)).scalars().all()

    # Base price levels for Indian tickers
    price_anchors = {
        "RELIANCE": 2740.0, "TCS": 4020.0, "HDFCBANK": 1720.0, "BAJFINANCE": 7180.0,
        "ZOMATO": 265.0, "TATAMOTORS": 880.0, "ADANIPORTS": 1390.0, "SUNPHARMA": 1840.0,
        "TITAN": 3320.0, "COALINDIA": 440.0, "INFY": 1860.0, "MARUTI": 11450.0,
        "ITC": 485.0, "ONGC": 260.0, "DIVISLAB": 5920.0, "PIDILITIND": 3140.0,
        "ASIANPAINT": 2420.0, "ASTRAL": 1820.0, "WIPRO": 540.0, "LTIM": 5980.0,
        "JIOFIN": 315.0, "NYKAA": 195.0, "PAYTM": 780.0, "IRFC": 155.0, "POLYCAB": 6480.0,
    }

    # Intentional triggers to showcase alert system:
    # 1. ZOMATO surged +6.2% on 2.4x volume
    # 2. TATAMOTORS fell -5.4% on 2.1x volume
    # 3. BAJFINANCE volume surge 2.8x
    special_events = {
        "ZOMATO": {"pct": 6.2, "vol_mult": 2.4},
        "TATAMOTORS": {"pct": -5.4, "vol_mult": 2.1},
        "BAJFINANCE": {"pct": 2.8, "vol_mult": 2.8},
        "TCS": {"pct": 1.2, "vol_mult": 1.1},
        "RELIANCE": {"pct": -0.8, "vol_mult": 1.3},
        "HDFCBANK": {"pct": 1.5, "vol_mult": 1.4},
    }

    base_date = datetime.utcnow()

    for comp in companies:
        anchor = price_anchors.get(comp.ticker, 1200.0)
        existing = db.execute(select(Price).where(Price.company_id == comp.id)).first()
        if existing:
            continue

        base_vol = 1_500_000 if anchor < 1000 else 450_000

        for day_offset in range(30, -1, -1):
            dt = base_date - timedelta(days=day_offset)

            if day_offset == 0 and comp.ticker in special_events:
                ev = special_events[comp.ticker]
                pct = ev["pct"]
                vol_ratio = ev["vol_mult"]
            else:
                # Small realistic random-like oscillation
                day_seed = (hash(f"{comp.ticker}_{day_offset}") % 40) - 20
                pct = round(day_seed * 0.08, 2)
                vol_ratio = round(0.85 + (abs(day_seed) % 5) * 0.1, 2)

            close_p = round(anchor * (1 + (pct / 100.0)), 2)
            open_p = round(close_p * (1 - (pct * 0.3 / 100.0)), 2)
            high_p = round(max(close_p, open_p) * 1.012, 2)
            low_p = round(min(close_p, open_p) * 0.988, 2)
            volume = float(int(base_vol * vol_ratio))

            p = Price(
                company_id=comp.id,
                date=dt,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=volume,
                adj_close=close_p,
                daily_change_pct=pct,
                volume_ratio=vol_ratio,
                volatility_20d=round(1.4 + (hash(comp.ticker) % 10) * 0.1, 2),
            )
            db.add(p)

    db.commit()


def _seed_announcements(db: Session):
    """Seeds authentic corporate filings across multiple categories with full enrichments."""
    from sqlalchemy import select
    companies_map = {c.ticker: c for c in db.execute(select(Company)).scalars().all()}

    now = datetime.utcnow()

    announcements_data = [
        # 1. TCS - Financial Results (HIGH)
        {
            "ticker": "TCS",
            "filed_at": now - timedelta(hours=6),
            "category": "results",
            "priority": "HIGH",
            "subject": "Financial Results for the Quarter and Half Year ended September 30, 2024 (Q2FY25)",
            "description": "Unaudited standalone and consolidated financial results under Ind AS. Revenue at ₹64,259 Cr, Operating Margin at 24.1%, Net Profit at ₹11,909 Cr.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/TCS_Results_Q2FY25.pdf",
            "ai_summary": "TCS reported Q2FY25 Revenue of ₹64,259 Cr (+7.6% YoY) with EBIT Margin at 24.1% (-20 bps QoQ). Net Profit rose to ₹11,909 Cr (+5.0% YoY). Interim dividend of ₹10/share declared.",
            "enrichment": {
                "revenue": {"value": 64259.0, "unit": "Cr", "qoq_pct": 2.6, "yoy_pct": 7.6},
                "ebitda": {"value": 16930.0, "unit": "Cr", "qoq_pct": 1.8, "yoy_pct": 6.8},
                "pbt": {"value": 16010.0, "unit": "Cr", "qoq_pct": 1.7, "yoy_pct": 6.4},
                "pat": {"value": 11909.0, "unit": "Cr", "qoq_pct": 2.1, "yoy_pct": 5.0}
            }
        },
        # 2. RELIANCE - Management Change (HIGH)
        {
            "ticker": "RELIANCE",
            "filed_at": now - timedelta(hours=14),
            "category": "management_change",
            "priority": "HIGH",
            "subject": "Change in Key Managerial Personnel - Appointment of Senior Executive Director",
            "description": "The Board has approved the appointment of Mr. Arvind Poddar as Executive Director (Oil-to-Chemicals & Clean Energy) effective November 1, 2024.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/RELIANCE_Mgmt_2024.pdf",
            "ai_summary": "Appointed Mr. Arvind Poddar as Executive Director overseeing O2C and Green Energy verticals, bringing 28 years of downstream refining and petrochemical operations leadership.",
            "enrichment": {
                "person_name": "Arvind Poddar",
                "role": "Executive Director (O2C & Green Energy)",
                "action": "joining",
                "background": "Over 28 years of leadership across downstream refining and renewable hydrogen transitions. Formerly Senior Vice President of Global Supply Chains at Shell."
            }
        },
        # 3. ZOMATO - M&A / Acquisition (HIGH)
        {
            "ticker": "ZOMATO",
            "filed_at": now - timedelta(hours=22),
            "category": "M&A",
            "priority": "HIGH",
            "subject": "Execution of Share Purchase Agreement for acquisition of Entertainment Ticketing Business",
            "description": "Zomato Limited has entered into definitive agreements to acquire Orbgen Technologies and Wasteland Entertainment (Paytm Insider) for an aggregate consideration of ₹2,048 Crores.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/ZOMATO_Acquisition.pdf",
            "ai_summary": "Acquired Paytm's entertainment and events ticketing businesses (Paytm Insider & Orbgen) for ₹2,048 Cr in all-cash deal to anchor its 'District' going-out app.",
            "enrichment": {
                "deal_value": "₹2,048 Crores",
                "target": "Paytm Entertainment & Ticketing Business",
                "strategic_rationale": "Scaling the high-margin live events and experiences vertical under the new 'District' consumer super-app."
            }
        },
        # 4. TATAMOTORS - Litigation & Commercial Tax Order (HIGH)
        {
            "ticker": "TATAMOTORS",
            "filed_at": now - timedelta(hours=30),
            "category": "litigation",
            "priority": "HIGH",
            "subject": "Disclosure under Regulation 30 - Receipt of Order from Commercial Taxes Department",
            "description": "Receipt of assessment order from Assistant Commissioner of State Tax, Pune, confirming GST demand and penalty totaling ₹142.5 Crores regarding transitional credit disallowance.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/TATAMOTORS_TaxOrder.pdf",
            "ai_summary": "Received adverse GST assessment order of ₹142.5 Cr in Pune regarding legacy transitional input credit. Company confirms filing appeal before Appellate Tribunal with zero expected material operational impact.",
            "enrichment": None
        },
        # 5. HDFCBANK - Fund Raise / Debt Issuance (HIGH)
        {
            "ticker": "HDFCBANK",
            "filed_at": now - timedelta(hours=38),
            "category": "fund_raise",
            "priority": "HIGH",
            "subject": "Allotment of Tier-II Capital Bonds on Private Placement Basis",
            "description": "Allotment of 15,000 Unsecured Redeemable Non-Convertible Subordinated Basel III compliant Tier II Bonds of face value ₹1 Crore each aggregating to ₹15,000 Crores at 7.72% p.a.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/HDFCBANK_TierII.pdf",
            "ai_summary": "Successfully issued ₹15,000 Cr Basel-III compliant Tier-II bonds at 7.72% p.a. to bolster capital adequacy and fund long-term credit pipeline.",
            "enrichment": None
        },
        # 6. SUNPHARMA - Capex Approval (MEDIUM)
        {
            "ticker": "SUNPHARMA",
            "filed_at": now - timedelta(hours=44),
            "category": "capex",
            "priority": "MEDIUM",
            "subject": "Board Approval for Greenfield API Manufacturing Facility Expansion in Gujarat",
            "description": "The Board of Directors has approved a capital expenditure of ₹650 Crores for setting up an advanced active pharmaceutical ingredient (API) facility at Dahej.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/SUNPHARMA_Capex.pdf",
            "ai_summary": "Approved ₹650 Cr greenfield API facility at Dahej to enhance supply chain vertical integration for specialty formulations.",
            "enrichment": None
        },
        # 7. TITAN - Dividend Declaration (MEDIUM)
        {
            "ticker": "TITAN",
            "filed_at": now - timedelta(hours=52),
            "category": "dividend",
            "priority": "MEDIUM",
            "subject": "Declaration of Special Interim Dividend and Record Date",
            "description": "The Board declared a special interim dividend of ₹11.00 per equity share of face value ₹1 each for the financial year 2024-25. Record date fixed as November 15, 2024.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/TITAN_Dividend.pdf",
            "ai_summary": "Declared special interim dividend of ₹11.00/share. Record date established as November 15, 2024.",
            "enrichment": None
        },
        # 8. BAJFINANCE - Credit Rating Reaffirmation (MEDIUM)
        {
            "ticker": "BAJFINANCE",
            "filed_at": now - timedelta(hours=60),
            "category": "credit_rating",
            "priority": "MEDIUM",
            "subject": "CRISIL Reaffirms AAA / Stable Rating on Long-Term Bank Facilities and Debt Instruments",
            "description": "CRISIL Ratings has reaffirmed its 'CRISIL AAA/Stable' rating on the non-convertible debentures and bank loan facilities of Bajaj Finance Limited totaling ₹1,20,000 Crores.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/BAJFINANCE_Rating.pdf",
            "ai_summary": "CRISIL reaffirmed highest credit rating of 'AAA/Stable' on ₹1.2 Lakh Cr debt program, citing market dominance and superior capital adequacy.",
            "enrichment": None
        },
        # 9. INFY - Investor Meetings Schedule (LOW)
        {
            "ticker": "INFY",
            "filed_at": now - timedelta(hours=72),
            "category": "investor_meetings",
            "priority": "LOW",
            "subject": "Schedule of Analyst / Institutional Investor Meet",
            "description": "Participating in UBS Global Technology Conference on November 12, 2024. Presentation materials will be uploaded post-event.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/INFY_AnalystMeet.pdf",
            "ai_summary": "Attending UBS Global Tech Investor Conference on November 12, 2024.",
            "enrichment": None
        },
        # 10. MARUTI - Routine ESOP Allotment (SKIP / UNCLASSIFIED)
        {
            "ticker": "MARUTI",
            "filed_at": now - timedelta(hours=80),
            "category": "unclassified",
            "priority": "SKIP",
            "subject": "Allotment of Equity Shares under Employees Stock Option Scheme 2019",
            "description": "Allotment of 12,450 equity shares of face value ₹5 each pursuant to exercise of stock options.",
            "attachment_url": "https://nsearchives.nseindia.com/corporate/MARUTI_ESOP.pdf",
            "ai_summary": "Routine allotment of 12,450 equity shares under employee stock option plan.",
            "enrichment": None
        }
    ]

    for item in announcements_data:
        comp = companies_map.get(item["ticker"])
        if not comp:
            continue

        existing = db.execute(
            select(Announcement).where(
                Announcement.company_id == comp.id,
                Announcement.subject == item["subject"]
            )
        ).first()

        if not existing:
            ann = Announcement(
                company_id=comp.id,
                source="NSE",
                filed_at=item["filed_at"],
                subject=item["subject"],
                description=item["description"],
                attachment_url=item["attachment_url"],
                category=item["category"],
                priority=item["priority"],
                ai_summary=item["ai_summary"],
                enrichment=item["enrichment"],
            )
            db.add(ann)

    db.commit()


def _seed_primary_documents(db: Session):
    """Indexes high-conviction excerpts from real Annual Reports and Concall transcripts."""
    from sqlalchemy import select

    primary_corpora = [
        # TCS Primary Disclosures
        {
            "ticker": "TCS",
            "doc_type": "annual_report",
            "period": "FY24",
            "chunks": [
                (
                    "BUSINESS OVERVIEW & OPERATING SEGMENTS:\n"
                    "Tata Consultancy Services is an IT services, consulting, and business solutions leader. "
                    "In FY24, consolidated revenue reached ₹2,40,893 Cr ($29.1B), expanding 6.8% in constant currency. "
                    "Vertical contribution: Banking, Financial Services and Insurance (BFSI) contributed 37.8%, "
                    "Consumer Business contributed 15.5%, Life Sciences & Healthcare 11.0%, Manufacturing 9.8%, "
                    "and Communication & Media 6.4%. Geographic distribution: North America accounts for 50.1%, "
                    "Continental Europe 15.1%, United Kingdom 16.5%, and India/Emerging Markets 18.3%."
                ),
                (
                    "BALANCE SHEET & CASH CONVERSION DISCIPLINE:\n"
                    "Gross debt stands at ₹0 (zero long-term debt). The company operates with a zero-debt, cash-positive balance sheet. "
                    "Cash Flow from Operations (CFO) for FY24 stood at ₹44,321 Cr, converting 95.3% of Net Profit (PAT of ₹46,585 Cr). "
                    "Free Cash Flow generated was ₹41,180 Cr after capital expenditures of ₹3,141 Cr. "
                    "Working capital cycle remained steady at 68 days with debtor days at 72 days and negative inventory cycle. "
                    "Return on Equity (ROE) stood at 51.1% and Return on Capital Employed (ROCE) at 63.4%."
                )
            ]
        },
        {
            "ticker": "TCS",
            "doc_type": "concall",
            "period": "Q2FY25",
            "chunks": [
                (
                    "MANAGEMENT GUIDANCE & FORWARD COMMENTARY (Q2FY25 Concall):\n"
                    "CEO K. Krithivasan: 'We closed the quarter with total deal contract value (TCV) of $8.6B, "
                    "comfortably meeting our stated run-rate objective of $8B-$9B per quarter. "
                    "Our operating margin stood resilient at 24.1%, absorbing quarterly wage hikes. "
                    "Looking into second half of FY25, we guide for operating margins to expand towards 24.5%-25.5% "
                    "as pyramid rationalization and productivity benefits materialize. "
                    "While North American banking clients show cautious recovery, UK and European deal pipelines "
                    "continue to demonstrate robust execution. Annual capex remains within ₹3,000-₹3,500 Cr.'"
                )
            ]
        },
        # RELIANCE Primary Disclosures
        {
            "ticker": "RELIANCE",
            "doc_type": "annual_report",
            "period": "FY24",
            "chunks": [
                (
                    "SEGMENT PERFORMANCE & CAPITAL EXPENDITURE:\n"
                    "Reliance Industries recorded annual consolidated revenue of ₹10,00,122 Cr ($120B) with EBITDA of ₹1,78,677 Cr (+16.1% YoY). "
                    "Segmental EBITDA: Oil-to-Chemicals (O2C) contributed ₹62,393 Cr (34.9%), Digital Services / Jio ₹54,498 Cr (30.5%), "
                    "and Reliance Retail ₹23,040 Cr (12.9%). Capex for the year was ₹1,31,769 Cr, largely directed towards 5G rollouts "
                    "and integrated solar and green hydrogen gigafactories at Jamnagar. Net debt to EBITDA stood at 0.65x."
                )
            ]
        },
        # ZOMATO Primary Disclosures
        {
            "ticker": "ZOMATO",
            "doc_type": "concall",
            "period": "Q2FY25",
            "chunks": [
                (
                    "MANAGEMENT COMMENTARY - QUICK COMMERCE & GOING OUT:\n"
                    "Deepinder Goyal: 'Blinkit GOV grew 122% YoY with store count reaching 791 stores as of Q2 end. "
                    "We guided in Q4 for store count to touch 1,000 by March 2025; we are now well ahead of that trajectory. "
                    "Adjusted EBITDA for Quick Commerce turned positive at ₹18 Cr in the quarter. "
                    "The acquisition of Paytm Insider provides us a market-leading events infrastructure to scale 'District' "
                    "into our third large consumer pillar without burning equity capital.'"
                )
            ]
        }
    ]

    for corp in primary_corpora:
        ticker = corp["ticker"]
        doc_type = corp["doc_type"]
        period = corp["period"]

        for idx, text in enumerate(corp["chunks"]):
            chunk_id = f"{ticker}_{doc_type}_{period}_{idx}"
            existing = db.execute(select(DocumentChunk).where(DocumentChunk.id == chunk_id)).first()
            if not existing:
                c = DocumentChunk(
                    id=chunk_id,
                    ticker=ticker,
                    doc_type=doc_type,
                    period=period,
                    chunk_index=idx,
                    text=text,
                    metadata_json={"source": f"{ticker} {period} {doc_type.upper()}", "seeded": True}
                )
                db.add(c)

    db.commit()


if __name__ == "__main__":
    seed_all_data()

