"""
FINN - Configuration & Constants
"""
import os
import sys
from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

load_dotenv()

# ── API Keys ────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Announcement Categories (from ENAM reference doc) ───────────────────────
ANNOUNCEMENT_CATEGORIES = [
    "results",
    "M&A",
    "fund_raise",
    "management_change",
    "litigation",
    "insider_trading",
    "earnings_call",
    "investor_meetings",
    "credit_rating",
    "dividend",
    "bonus_split",
    "capex",
    "press_release",
    "postal_ballot",
    "agm_egm",
    "pledging",
    "unclassified",
]

# ── Priority Mapping ────────────────────────────────────────────────────────
PRIORITY_MAP = {
    "results":           "HIGH",
    "M&A":               "HIGH",
    "management_change": "HIGH",
    "litigation":        "HIGH",
    "fund_raise":        "HIGH",
    "credit_rating":     "MEDIUM",
    "capex":             "MEDIUM",
    "dividend":          "MEDIUM",
    "insider_trading":   "MEDIUM",
    "pledging":          "MEDIUM",
    "earnings_call":     "MEDIUM",
    "press_release":     "LOW",
    "investor_meetings": "LOW",
    "bonus_split":       "LOW",
    "agm_egm":           "LOW",
    "postal_ballot":     "LOW",
    "unclassified":      "SKIP",
}

# ── Model Routing ───────────────────────────────────────────────────────────
CHEAP_MODEL = "gemini-1.5-flash"
STRONG_MODEL = "gpt-4o"

# ── Model Cost per 1M tokens (approx USD) ──────────────────────────────────
MODEL_COSTS = {
    "gemini-1.5-flash":     {"input": 0.075,  "output": 0.30},
    "gemini-1.5-pro":       {"input": 1.25,   "output": 5.00},
    "gpt-4o-mini":          {"input": 0.15,   "output": 0.60},
    "gpt-4o":               {"input": 2.50,   "output": 10.00},
    "claude-3-5-sonnet":    {"input": 3.00,   "output": 15.00},
}

# ── Financial Terms (for structured extraction) ────────────────────────────
HEADLINE_METRICS = ["Revenue", "EBITDA", "PBT", "PAT"]

# ── Default Alert Thresholds ────────────────────────────────────────────────
DEFAULT_ALERTS = {
    "price_move_pct": 5.0,
    "volume_multiplier": 2.0,
    "announcement_categories": ["results", "M&A", "management_change", "litigation"],
}

# ── ChromaDB ────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.path.join(BACKEND_DIR, "chroma_db")
EMBEDDING_MODEL = "text-embedding-3-small"

# ── Data fetch settings ─────────────────────────────────────────────────────
PRICE_HISTORY_PERIOD = "6mo"
NSE_BASE_URL = "https://www.nseindia.com"
NSE_API_ANNOUNCEMENTS = f"{NSE_BASE_URL}/api/corporate-announcements"
NSE_RSS_URL = "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"
SCREENER_BASE_URL = "https://www.screener.in/company"
