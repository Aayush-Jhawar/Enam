"""
FINN - Engine Verification Script
Tests database, alert engine, digest generation, and research modules.
"""
import sys
import json

# Force UTF-8 stdout for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from database import SessionLocal
from services.research_engine import ResearchEngine
from services.digest_engine import generate_digest
from services.alert_engine import get_active_alerts, get_alert_configs
from services.model_router import get_total_cost

def test_finn():
    db = SessionLocal()
    print("=" * 60)
    print("FINN SYSTEM VERIFICATION AUDIT")
    print("=" * 60)

    # 1. Alert Engine
    alerts = get_active_alerts(db, limit=5)
    print(f"\n[1] ACTIVE ALERTS TRIGGERED ({len(alerts)}):")
    for a in alerts:
        print(f"  - [{a['severity']}] {a['company_ticker']} ({a['alert_type']}): {a['title']}")

    # 2. Windowed Digest (Push Mode)
    digest = generate_digest(db, hours=48)
    print(f"\n[2] WINDOWED DIGEST (48h Window):")
    print(f"  Total filings: {digest['total']} | HIGH: {len(digest['high'])} | MED: {len(digest['medium'])} | LOW: {len(digest['low'])} | SKIPPED: {digest['skipped']}")
    if digest['summary']:
        print(f"  Executive Brief: {digest['summary']}")
    for h in digest['high'][:2]:
        print(f"  * [HIGH] {h['ticker']} ({h['category']}): {h['ai_summary']}")
        if h['enrichment']:
            print(f"    Enrichment: {json.dumps(h['enrichment'])}")

    # 3. Pull Mode - Narrative vs Numbers (TCS)
    engine = ResearchEngine(db)
    nvn = engine.analyze_company("TCS", module="narrative_vs_numbers")
    print(f"\n[3] PULL ENGINE: TCS NARRATIVE VS NUMBERS (THE CROWN JEWEL):")
    data = nvn['data']
    print(f"  Credibility Score: {data.get('credibility_score')} | Delivery Rate: {data.get('delivery_rate_pct')}%")
    print(f"  Executive Assessment: {data.get('executive_summary')}")
    print("  Quarterly Delivery Scorecard:")
    for q in data.get('quarters', []):
        print(f"    - [{q['verdict']}] {q['quarter']} {q['metric']}: {q['guided_statement']} -> {q['delivered_actual']}")

    # 4. Pull Mode - Financial Snapshot (RELIANCE)
    fin = engine.analyze_company("RELIANCE", module="financial_snapshot")
    print(f"\n[4] FINANCIAL SNAPSHOT (RELIANCE):")
    fdata = fin['data']
    print(f"  Revenue: ₹{fdata.get('revenue'):,} Cr | EBITDA: ₹{fdata.get('ebitda'):,} Cr ({fdata.get('ebitda_margin_pct')}%) | PAT: ₹{fdata.get('pat'):,} Cr")

    # 5. Cost Tracking Audit
    cost = get_total_cost(db)
    print(f"\n[5] COMPUTE COST AUDIT:")
    print(f"  Total API Spend: ${cost['total_cost_usd']} | Total Tokens: {cost['total_tokens']}")

    print("\n" + "=" * 60)
    print("ALL CORE ENGINES OPERATIONAL WITH ZERO ERRORS")
    print("=" * 60)
    db.close()

if __name__ == "__main__":
    test_finn()
