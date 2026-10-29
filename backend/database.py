"""
FINN - Database Models & Persistence
SQLAlchemy schema for portfolio companies, prices, exchange announcements,
alerts, research cache, and document chunks.
"""
import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    Text, Boolean, JSON, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.pool import StaticPool

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "finn.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    yf_ticker = Column(String(25), nullable=False)
    name = Column(String(200), nullable=False)
    sector = Column(String(100), nullable=False)
    in_portfolio = Column(Boolean, default=False, index=True)
    market_cap_category = Column(String(20), default="Large Cap")  # Large, Mid, Small
    created_at = Column(DateTime, default=datetime.utcnow)

    prices = relationship("Price", back_populates="company", cascade="all, delete-orphan")
    announcements = relationship("Announcement", back_populates="company", cascade="all, delete-orphan")
    alerts = relationship("TriggeredAlert", back_populates="company", cascade="all, delete-orphan")


class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    adj_close = Column(Float)

    # Derived EOD Signals
    daily_change_pct = Column(Float)
    volume_ratio = Column(Float)        # Volume / 20-day moving average volume
    volatility_20d = Column(Float)      # 20-day standard deviation of daily returns

    company = relationship("Company", back_populates="prices")

    __table_args__ = (
        Index("ix_prices_company_date", "company_id", "date", unique=True),
    )


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    source = Column(String(15), default="NSE")
    filed_at = Column(DateTime, nullable=False, index=True)
    subject = Column(Text, nullable=False)
    description = Column(Text)
    attachment_url = Column(Text)

    # Classification & Synthesis
    category = Column(String(50), index=True)
    priority = Column(String(10), index=True)  # HIGH, MEDIUM, LOW, SKIP
    ai_summary = Column(Text)
    enrichment = Column(JSON)                 # Structured extraction (QoQ/YoY for results, bio for mgmt)

    company = relationship("Company", back_populates="announcements")

    __table_args__ = (
        Index("ix_ann_company_filed", "company_id", "filed_at"),
    )


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(30), nullable=False)     # price_move, volume_spike, announcement
    threshold = Column(Float)                           # e.g., 5.0 for 5%, 2.0 for 2x volume
    direction = Column(String(10), default="both")      # up, down, both
    categories = Column(JSON)                           # ["results", "M&A", "management_change"]
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TriggeredAlert(Base):
    __tablename__ = "triggered_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    alert_type = Column(String(30), nullable=False)
    title = Column(String(300), nullable=False)
    detail = Column(Text)
    value = Column(Float)
    threshold = Column(Float)
    severity = Column(String(20), default="HIGH")       # HIGH, MEDIUM, INFO
    triggered_at = Column(DateTime, default=datetime.utcnow, index=True)
    dismissed = Column(Boolean, default=False, index=True)

    company = relationship("Company", back_populates="alerts")


class ResearchCache(Base):
    __tablename__ = "research_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    module = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    model_used = Column(String(50))
    input_hash = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

    __table_args__ = (
        Index("ix_research_ticker_module", "ticker", "module"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(120), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    doc_type = Column(String(50), nullable=False, index=True)  # annual_report, concall
    period = Column(String(30))                               # e.g. FY24, Q2FY25
    chunk_index = Column(Integer)
    text = Column(Text, nullable=False)
    metadata_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class LLMCallLog(Base):
    __tablename__ = "llm_call_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(50), nullable=False)
    task = Column(String(100), nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Initializes tables and ensures schema exists."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI database session generator."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Canonical Watchlist Definitions ─────────────────────────────────────────

PORTFOLIO_COMPANIES = [
    ("RELIANCE",   "RELIANCE.NS",   "Reliance Industries",       "Conglomerate",    "Large Cap"),
    ("TCS",        "TCS.NS",        "Tata Consultancy Services", "IT Services",     "Large Cap"),
    ("HDFCBANK",   "HDFCBANK.NS",   "HDFC Bank",                 "Banking",         "Large Cap"),
    ("BAJFINANCE", "BAJFINANCE.NS", "Bajaj Finance",             "NBFC",            "Large Cap"),
    ("ZOMATO",     "ZOMATO.NS",     "Zomato Limited",            "Consumer Tech",   "Large Cap"),
    ("TATAMOTORS", "TATAMOTORS.NS", "Tata Motors",               "Automobile",      "Large Cap"),
    ("ADANIPORTS", "ADANIPORTS.NS", "Adani Ports & SEZ",         "Infrastructure",  "Large Cap"),
    ("SUNPHARMA",  "SUNPHARMA.NS",  "Sun Pharmaceutical",        "Pharma",          "Large Cap"),
    ("TITAN",      "TITAN.NS",      "Titan Company",             "Consumer / Gems", "Large Cap"),
    ("COALINDIA",  "COALINDIA.NS",  "Coal India",                "Energy / PSU",    "Large Cap"),
    ("INFY",       "INFY.NS",       "Infosys",                   "IT Services",     "Large Cap"),
    ("MARUTI",     "MARUTI.NS",     "Maruti Suzuki India",       "Automobile",      "Large Cap"),
    ("ITC",        "ITC.NS",        "ITC Limited",               "FMCG",            "Large Cap"),
    ("ONGC",       "ONGC.NS",       "Oil & Natural Gas Corp",    "Energy",          "Large Cap"),
    ("DIVISLAB",   "DIVISLAB.NS",   "Divi's Laboratories",       "Pharma",          "Large Cap"),
    ("PIDILITIND", "PIDILITIND.NS", "Pidilite Industries",       "Specialty Chem",  "Large Cap"),
    ("ASIANPAINT", "ASIANPAINT.NS", "Asian Paints",              "Paints / Chem",   "Large Cap"),
    ("ASTRAL",     "ASTRAL.NS",     "Astral Limited",            "Building Mat",    "Mid Cap"),
    ("WIPRO",      "WIPRO.NS",      "Wipro Limited",             "IT Services",     "Large Cap"),
    ("LTIM",       "LTIM.NS",       "LTIMindtree",               "IT Services",     "Large Cap"),
]

ADHOC_COMPANIES = [
    ("JIOFIN",     "JIOFIN.NS",     "Jio Financial Services",    "Fintech",         "Large Cap"),
    ("NYKAA",      "NYKAA.NS",      "FSN E-Commerce (Nykaa)",    "Consumer Tech",   "Mid Cap"),
    ("PAYTM",      "PAYTM.NS",      "One97 Communications",      "Fintech",         "Mid Cap"),
    ("IRFC",       "IRFC.NS",       "Indian Railway Finance Corp","PSU / Finance",  "Large Cap"),
    ("POLYCAB",    "POLYCAB.NS",    "Polycab India",             "Cables / Wire",   "Large Cap"),
]


def seed_companies_and_alerts(db):
    """Populates baseline companies and default monitoring thresholds."""
    from sqlalchemy import select

    # Seed Portfolio
    for ticker, yf_ticker, name, sector, mcap in PORTFOLIO_COMPANIES:
        existing = db.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
        if not existing:
            db.add(Company(
                ticker=ticker,
                yf_ticker=yf_ticker,
                name=name,
                sector=sector,
                in_portfolio=True,
                market_cap_category=mcap
            ))

    # Seed Ad-hoc
    for ticker, yf_ticker, name, sector, mcap in ADHOC_COMPANIES:
        existing = db.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
        if not existing:
            db.add(Company(
                ticker=ticker,
                yf_ticker=yf_ticker,
                name=name,
                sector=sector,
                in_portfolio=False,
                market_cap_category=mcap
            ))

    # Seed Default Alert Configurations if empty
    configs_count = db.execute(select(AlertConfig)).scalars().all()
    if not configs_count:
        db.add(AlertConfig(
            alert_type="price_move",
            threshold=5.0,
            direction="both",
            enabled=True
        ))
        db.add(AlertConfig(
            alert_type="volume_spike",
            threshold=2.0,
            direction="up",
            enabled=True
        ))
        db.add(AlertConfig(
            alert_type="announcement",
            categories=["results", "M&A", "management_change", "litigation", "fund_raise"],
            enabled=True
        ))

    db.commit()
