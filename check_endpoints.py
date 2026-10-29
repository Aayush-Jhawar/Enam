"""
FINN - Complete Endpoint Health Check
Runs all API routes through the ASGI TestClient (no real network needed).
Prints a clean pass/fail table, then exits non-zero if any test failed.
"""
import sys
import json
import traceback

# Force UTF-8 for the Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Make sure the backend folder is on sys.path ─────────────────────────────
import os
ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from starlette.testclient import TestClient
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

results = []


def check(label, fn):
    try:
        status, detail = fn()
        results.append((status, label, detail))
    except Exception as e:
        results.append((FAIL, label, traceback.format_exc().strip().split("\n")[-1]))


# ── 1. System ────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200, f"HTTP {r.status_code}"
    d = r.json()
    assert d["status"] == "operational"
    db = d["database"]
    assert db["companies"] >= 25, f"Expected ≥25 companies, got {db['companies']}"
    assert db["prices_recorded"] >= 700, f"Expected ≥700 prices, got {db['prices_recorded']}"
    assert db["announcements"] >= 10, f"Expected ≥10 announcements, got {db['announcements']}"
    assert db["active_alerts"] >= 5, f"Expected ≥5 alerts, got {db['active_alerts']}"
    return PASS, f"companies={db['companies']} prices={db['prices_recorded']} alerts={db['active_alerts']}"

check("GET /api/health", test_health)


# ── 2. Portfolio & Companies ─────────────────────────────────────────────────

def test_companies_all():
    r = client.get("/api/companies")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 25
    tickers = [c["ticker"] for c in data]
    for t in ["TCS", "RELIANCE", "HDFCBANK", "ZOMATO", "BAJFINANCE"]:
        assert t in tickers, f"{t} missing from company list"
    return PASS, f"{len(data)} companies returned"

check("GET /api/companies (all)", test_companies_all)


def test_companies_portfolio_filter():
    r = client.get("/api/companies?in_portfolio=true")
    assert r.status_code == 200
    data = r.json()
    assert all(c["in_portfolio"] for c in data)
    assert len(data) == 20
    return PASS, f"{len(data)} portfolio companies"

check("GET /api/companies?in_portfolio=true", test_companies_portfolio_filter)


def test_companies_price_data():
    r = client.get("/api/companies?in_portfolio=true")
    data = r.json()
    with_price = [c for c in data if c["close"] is not None]
    assert len(with_price) >= 15, f"Only {len(with_price)} companies have price data"
    # check sample fields
    c = with_price[0]
    assert "daily_change_pct" in c
    assert "volume_ratio" in c
    return PASS, f"{len(with_price)}/{len(data)} companies have EOD price data"

check("GET /api/companies — price data present", test_companies_price_data)


# ── 3. PUSH MODE ─────────────────────────────────────────────────────────────

def test_digest_24h():
    r = client.get("/api/push/digest?hours=24")
    assert r.status_code == 200
    d = r.json()
    assert "window" in d and d["window"] == "24h"
    assert "high" in d and "medium" in d and "low" in d
    assert d["total"] >= 0
    return PASS, f"total={d['total']} high={len(d['high'])} med={len(d['medium'])} low={len(d['low'])}"

check("GET /api/push/digest?hours=24", test_digest_24h)


def test_digest_48h():
    r = client.get("/api/push/digest?hours=48")
    assert r.status_code == 200
    d = r.json()
    assert len(d["high"]) >= 3, f"Expected ≥3 HIGH items in 48h, got {len(d['high'])}"
    # Confirm results enrichment is populated
    results_items = [h for h in d["high"] if h["category"] == "results"]
    if results_items:
        en = results_items[0]["enrichment"]
        assert en is not None, "Results enrichment missing"
        assert "revenue" in en
        assert "pat" in en
    return PASS, f"high={len(d['high'])} results_enriched={len(results_items)}"

check("GET /api/push/digest?hours=48 (enrichment check)", test_digest_48h)


def test_digest_7d():
    r = client.get("/api/push/digest?hours=168")
    assert r.status_code == 200
    d = r.json()
    assert d["window"] == "168h"
    return PASS, f"total={d['total']}"

check("GET /api/push/digest?hours=168", test_digest_7d)


def test_digest_ticker_filter():
    r = client.get("/api/push/digest?hours=168&ticker=TCS")
    assert r.status_code == 200
    d = r.json()
    all_items = d["high"] + d["medium"] + d["low"]
    for item in all_items:
        assert item["ticker"] == "TCS", f"Got non-TCS ticker: {item['ticker']}"
    return PASS, f"ticker=TCS total={d['total']}"

check("GET /api/push/digest?ticker=TCS", test_digest_ticker_filter)


def test_alerts_list():
    r = client.get("/api/push/alerts")
    assert r.status_code == 200
    alerts = r.json()
    assert len(alerts) >= 5
    for a in alerts:
        assert "title" in a
        assert "severity" in a
        assert "company_ticker" in a
    return PASS, f"{len(alerts)} active alerts"

check("GET /api/push/alerts", test_alerts_list)


def test_alert_configs():
    r = client.get("/api/push/alert-configs")
    assert r.status_code == 200
    configs = r.json()
    assert len(configs) == 3
    types = {c["alert_type"] for c in configs}
    assert "price_move" in types
    assert "volume_spike" in types
    assert "announcement" in types
    return PASS, f"{len(configs)} configs: {', '.join(sorted(types))}"

check("GET /api/push/alert-configs", test_alert_configs)


def test_update_alert_config():
    r = client.put("/api/push/alert-configs/1", json={"threshold": 6.0})
    assert r.status_code == 200
    d = r.json()
    assert d["threshold"] == 6.0
    # Reset it back
    client.put("/api/push/alert-configs/1", json={"threshold": 5.0})
    return PASS, "threshold updated to 6.0 and reset to 5.0"

check("PUT /api/push/alert-configs/1", test_update_alert_config)


def test_alert_update_not_found():
    r = client.put("/api/push/alert-configs/9999", json={"threshold": 5.0})
    assert r.status_code == 404
    return PASS, "404 on unknown config_id=9999"

check("PUT /api/push/alert-configs/9999 (404 test)", test_alert_update_not_found)


def test_push_refresh():
    r = client.post("/api/push/refresh")
    assert r.status_code == 200
    d = r.json()
    assert "status" in d
    return PASS, f"status={d['status']} price_alerts={d.get('new_price_alerts')} ann_alerts={d.get('new_announcement_alerts')}"

check("POST /api/push/refresh", test_push_refresh)


# ── 4. PULL MODE ─────────────────────────────────────────────────────────────

def test_research_tcs_nvn():
    r = client.get("/api/pull/research/TCS?module=narrative_vs_numbers")
    assert r.status_code == 200
    d = r.json()
    assert d["module"] == "narrative_vs_numbers"
    data = d["data"]
    assert "credibility_score" in data
    assert "delivery_rate_pct" in data
    quarters = data.get("quarters", [])
    assert len(quarters) >= 4, f"Expected ≥4 quarters, got {len(quarters)}"
    verdicts = {q["verdict"] for q in quarters}
    assert verdicts.issubset({"HIT", "MISS", "IN-LINE"}), f"Unknown verdicts: {verdicts}"
    return PASS, f"credibility={data['credibility_score']} delivery={data['delivery_rate_pct']}% quarters={len(quarters)}"

check("GET /api/pull/research/TCS?module=narrative_vs_numbers", test_research_tcs_nvn)


def test_research_reliance_financial():
    r = client.get("/api/pull/research/RELIANCE?module=financial_snapshot")
    assert r.status_code == 200
    d = r.json()
    data = d["data"]
    assert "revenue" in data
    assert "ebitda" in data
    assert "pat" in data
    assert "roe_pct" in data
    return PASS, f"revenue={data.get('revenue')} ebitda_margin={data.get('ebitda_margin_pct')}%"

check("GET /api/pull/research/RELIANCE?module=financial_snapshot", test_research_reliance_financial)


def test_research_tcs_business_snapshot():
    r = client.get("/api/pull/research/TCS?module=business_snapshot")
    assert r.status_code == 200
    d = r.json()
    data = d["data"]
    assert "summary" in data
    assert "segments" in data
    assert len(data["segments"]) >= 1
    return PASS, f"segments={len(data['segments'])}"

check("GET /api/pull/research/TCS?module=business_snapshot", test_research_tcs_business_snapshot)


def test_research_tcs_trajectory():
    r = client.get("/api/pull/research/TCS?module=trajectory")
    assert r.status_code == 200
    d = r.json()
    data = d["data"]
    assert "revenue_cagr_3yr" in data
    return PASS, f"cagr={data.get('revenue_cagr_3yr')}"

check("GET /api/pull/research/TCS?module=trajectory", test_research_tcs_trajectory)


def test_research_tcs_balance_sheet():
    r = client.get("/api/pull/research/TCS?module=balance_sheet")
    assert r.status_code == 200
    d = r.json()
    data = d["data"]
    assert "gross_debt_cr" in data
    return PASS, f"gross_debt={data.get('gross_debt_cr')}"

check("GET /api/pull/research/TCS?module=balance_sheet", test_research_tcs_balance_sheet)


def test_research_tcs_cash_quality():
    r = client.get("/api/pull/research/TCS?module=cash_quality")
    assert r.status_code == 200
    d = r.json()
    data = d["data"]
    assert "cfo_to_pat_conversion_pct" in data
    return PASS, f"conversion={data.get('cfo_to_pat_conversion_pct')}%"

check("GET /api/pull/research/TCS?module=cash_quality", test_research_tcs_cash_quality)


def test_research_tcs_guidance():
    r = client.get("/api/pull/research/TCS?module=guidance")
    assert r.status_code == 200
    d = r.json()
    data = d["data"]
    assert "revenue_growth_guidance" in data
    return PASS, f"guidance={data.get('revenue_growth_guidance')}"

check("GET /api/pull/research/TCS?module=guidance", test_research_tcs_guidance)


def test_research_tcs_bull_bear():
    r = client.get("/api/pull/research/TCS?module=bull_vs_bear")
    assert r.status_code == 200
    d = r.json()
    data = d["data"]
    assert "bull_case" in data
    assert "bear_case" in data
    assert len(data["bull_case"]) >= 2
    assert len(data["bear_case"]) >= 2
    return PASS, f"bulls={len(data['bull_case'])} bears={len(data['bear_case'])}"

check("GET /api/pull/research/TCS?module=bull_vs_bear", test_research_tcs_bull_bear)


def test_research_adhoc_ticker():
    """Should work for any NSE ticker not in the pre-seeded portfolio"""
    r = client.get("/api/pull/research/POLYCAB?module=financial_snapshot")
    assert r.status_code == 200
    d = r.json()
    assert "data" in d
    return PASS, f"adhoc ticker POLYCAB worked, module={d.get('module')}"

check("GET /api/pull/research/POLYCAB (ad-hoc ticker)", test_research_adhoc_ticker)


def test_research_cache_hit():
    """Second call must use cache and return same data"""
    r1 = client.get("/api/pull/research/TCS?module=guidance")
    r2 = client.get("/api/pull/research/TCS?module=guidance")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["cached"] is True
    return PASS, "second call served from cache"

check("GET /api/pull/research/TCS caching", test_research_cache_hit)


# ── 5. Static Frontend Assets ─────────────────────────────────────────────────

def test_frontend_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "FINN" in r.text
    assert "<html" in r.text.lower()
    return PASS, f"HTML served, size={len(r.content)} bytes"

check("GET / (index.html)", test_frontend_root)


def test_frontend_css():
    r = client.get("/style.css")
    assert r.status_code == 200
    assert "phone-viewport-container" in r.text
    return PASS, f"CSS served, size={len(r.content)} bytes"

check("GET /style.css", test_frontend_css)


def test_frontend_js():
    r = client.get("/app.js")
    assert r.status_code == 200
    assert "loadPushDigest" in r.text
    return PASS, f"JS served, size={len(r.content)} bytes"

check("GET /app.js", test_frontend_js)


# ── 6. Audit ─────────────────────────────────────────────────────────────────

def test_cost_audit():
    r = client.get("/api/audit/costs")
    assert r.status_code == 200
    d = r.json()
    assert "total_cost_usd" in d
    assert "total_api_calls" in d
    return PASS, f"total_cost=${d['total_cost_usd']} calls={d['total_api_calls']}"

check("GET /api/audit/costs", test_cost_audit)


# ── 7. Dismiss Alert (mutating test) ─────────────────────────────────────────

def test_dismiss_alert():
    # Get first active alert id
    alerts = client.get("/api/push/alerts").json()
    if not alerts:
        return SKIP, "no alerts to dismiss"
    alert_id = alerts[0]["id"]
    r = client.post(f"/api/push/alerts/{alert_id}/dismiss")
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"
    # Verify it's gone from active feed
    remaining = client.get("/api/push/alerts").json()
    ids = [a["id"] for a in remaining]
    assert alert_id not in ids, "alert still showing after dismiss"
    return PASS, f"dismissed alert_id={alert_id}, remaining active={len(remaining)}"

check("POST /api/push/alerts/{id}/dismiss", test_dismiss_alert)


def test_dismiss_nonexistent():
    r = client.post("/api/push/alerts/999999/dismiss")
    assert r.status_code == 404
    return PASS, "404 on unknown alert_id=999999"

check("POST /api/push/alerts/999999/dismiss (404 test)", test_dismiss_nonexistent)


# ── Print Results ─────────────────────────────────────────────────────────────

TOTAL = len(results)
PASSED = sum(1 for s, _, _ in results if s == PASS)
FAILED = sum(1 for s, _, _ in results if s == FAIL)
SKIPPED = sum(1 for s, _, _ in results if s == SKIP)

print()
print("=" * 70)
print(f"  FINN ENDPOINT AUDIT — {TOTAL} checks")
print("=" * 70)

for status, label, detail in results:
    icon = "✓" if status == PASS else ("✗" if status == FAIL else "~")
    colour_label = f"[{status}]"
    print(f"  {icon} {colour_label:6s}  {label}")
    print(f"           └─ {detail}")

print()
print("=" * 70)
print(f"  Passed: {PASSED} / {TOTAL}   Failed: {FAILED}   Skipped: {SKIPPED}")
print("=" * 70)

sys.exit(0 if FAILED == 0 else 1)

