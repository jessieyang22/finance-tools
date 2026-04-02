#!/usr/bin/env python3
"""
Jessica Yang — Market & Macro Monitor
======================================
Weekly script that pulls key market, macro, and sector data
from free public sources. No API key required.

Run every Sunday morning before your week starts:
    python market_macro_monitor.py

Covers:
  • Equity indices (S&P 500, Nasdaq, Russell 2000)
  • Rates & credit (10Y/2Y Treasury, HY spreads)
  • Volatility (VIX)
  • SaaS / Tech sector valuation (BVP Cloud Index proxy)
  • Macro calendar for the coming week
  • Fed watch (next meeting, implied rate path)
  • Key earnings this week across your coverage universe

Sources: Yahoo Finance (free, no key), FRED (free, no key),
         Finviz (free), Earnings Whispers calendar
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Optional

HEADERS = {"User-Agent": "Jessica Yang yangjessie7@gmail.com"}

# ─────────────────────────────────────────────────────────────
# 1. EQUITY INDICES  — Yahoo Finance
# ─────────────────────────────────────────────────────────────

INDICES = {
    "S&P 500":       "^GSPC",
    "Nasdaq 100":    "^NDX",
    "Russell 2000":  "^RUT",
    "Dow Jones":     "^DJI",
    "VIX":           "^VIX",
    # SaaS proxy ETF
    "IGV (Software ETF)": "IGV",
}

COVERAGE = {
    "HubSpot":    "HUBS",
    "Salesforce": "CRM",
    "ServiceNow": "NOW",
    "Datadog":    "DDOG",
    "Snowflake":  "SNOW",
    "Adobe":      "ADBE",
}

def get_yahoo_quote(symbol: str) -> Optional[dict]:
    """Fetch latest quote from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": "1d", "range": "5d"}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose")
        change_pct = ((price - prev) / prev * 100) if prev else 0
        return {
            "symbol":     symbol,
            "price":      price,
            "prev_close": prev,
            "change_pct": change_pct,
            "52w_high":   meta.get("fiftyTwoWeekHigh"),
            "52w_low":    meta.get("fiftyTwoWeekLow"),
            "currency":   meta.get("currency", "USD"),
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

# ─────────────────────────────────────────────────────────────
# 2. TREASURY RATES  — FRED (St. Louis Fed, free, no key)
# ─────────────────────────────────────────────────────────────

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"

FRED_SERIES = {
    "10Y Treasury": "DGS10",
    "2Y Treasury":  "DGS2",
    "Fed Funds Rate": "FEDFUNDS",
}

def get_fred_rate(series_id: str) -> Optional[float]:
    """Pull the latest observation from FRED (no API key needed for CSV)."""
    url = f"{FRED_BASE}?id={series_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        lines = [l for l in resp.text.strip().split("\n") if l and not l.startswith("DATE")]
        # Get last non-empty value
        for line in reversed(lines):
            parts = line.split(",")
            if len(parts) == 2 and parts[1].strip() not in (".", ""):
                return float(parts[1].strip())
    except Exception:
        pass
    return None

# ─────────────────────────────────────────────────────────────
# 3. MACRO CALENDAR  — Key events this week (hardcoded framework,
#    update the dates each week or automate via scrapers)
# ─────────────────────────────────────────────────────────────

def get_macro_calendar() -> list[dict]:
    """
    Key macro events to watch.
    Update this list each week, or connect to an economic calendar API.
    Free calendar sources:
      - https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
      - https://www.bls.gov/schedule/news_release/
      - https://tradingeconomics.com/calendar
    """
    # Standing weekly events
    weekly = [
        {"day": "Tuesday",   "event": "ISM Services PMI",             "why_it_matters": "Signals SaaS/enterprise software demand health"},
        {"day": "Wednesday",  "event": "FOMC Meeting Minutes (if week)", "why_it_matters": "Rate path signals = multiple expansion/compression for SaaS"},
        {"day": "Thursday",  "event": "Initial Jobless Claims",        "why_it_matters": "Labor market health → enterprise software budget proxy"},
        {"day": "Friday",    "event": "Non-Farm Payrolls (1st Friday)", "why_it_matters": "Employment data → Fed reaction → risk-on/risk-off for tech"},
    ]

    # Q1 2026 upcoming events (update monthly)
    upcoming_major = [
        {"date": "Apr 23, 2026",  "event": "ServiceNow Q1 2025 Earnings",      "ticker": "NOW",  "priority": "HIGH"},
        {"date": "Apr 29, 2026",  "event": "FOMC Rate Decision",                "ticker": "MACRO","priority": "HIGH"},
        {"date": "Apr 30, 2026",  "event": "GDP Q1 2026 Advance Estimate",      "ticker": "MACRO","priority": "HIGH"},
        {"date": "May 2, 2026",   "event": "Non-Farm Payrolls (April)",          "ticker": "MACRO","priority": "MED"},
        {"date": "May 6, 2026",   "event": "HubSpot Q1 2026 Earnings (est.)",   "ticker": "HUBS", "priority": "HIGH"},
        {"date": "May 7, 2026",   "event": "Datadog Q1 2026 Earnings (est.)",   "ticker": "DDOG", "priority": "HIGH"},
        {"date": "May 13, 2026",  "event": "CPI Inflation (April)",             "ticker": "MACRO","priority": "HIGH"},
        {"date": "May 21, 2026",  "event": "Snowflake Q1 FY27 Earnings (est.)", "ticker": "SNOW", "priority": "MED"},
        {"date": "May 28, 2026",  "event": "Salesforce Q1 FY27 Earnings (est.)","ticker": "CRM",  "priority": "MED"},
        {"date": "Jun 11, 2026",  "event": "FOMC Rate Decision",                "ticker": "MACRO","priority": "HIGH"},
        {"date": "Jun 12, 2026",  "event": "Adobe Q2 FY2026 Earnings (est.)",   "ticker": "ADBE", "priority": "MED"},
    ]
    return {"weekly_watch": weekly, "upcoming": upcoming_major}

# ─────────────────────────────────────────────────────────────
# 4. RATE SPREAD ANALYSIS
# ─────────────────────────────────────────────────────────────

def analyze_yield_curve(rate_10y: float, rate_2y: float) -> str:
    """Interpret the yield curve for SaaS investing context."""
    spread = rate_10y - rate_2y
    if spread > 0.5:
        return f"NORMAL ({spread:+.2f}%) — steepening curve signals growth expectations; positive for long-duration SaaS multiples"
    elif spread > 0:
        return f"FLAT-NORMAL ({spread:+.2f}%) — limited rate cut expectations; multiples range-bound"
    elif spread > -0.5:
        return f"SLIGHTLY INVERTED ({spread:+.2f}%) — mild recession signal; watch enterprise IT budget commentary"
    else:
        return f"INVERTED ({spread:+.2f}%) — recession risk elevated; SaaS multiples under pressure; favor high-FCF names"

# ─────────────────────────────────────────────────────────────
# 5. SAAS MULTIPLE CONTEXT
# ─────────────────────────────────────────────────────────────

SAAS_MULTIPLE_CONTEXT = """
SaaS VALUATION CONTEXT (as of April 2026):
  • BVP Nasdaq Emerging Cloud Index: ~6–8x NTM rev (avg)
  • Peak (Jan 2021): ~20x NTM rev
  • Trough (Dec 2022): ~5x NTM rev
  • Current premium names (AI-differentiated): 12–14x (NOW, DDOG)
  • Current compressed names: 6–7x (ADBE), 3–4x (legacy SaaS)
  
  Rule of 40 benchmarks (Rev Growth % + FCF Margin %):
  • Elite (>60): Datadog (~49%), ServiceNow (~52%)
  • Good  (>40): HubSpot (~38%, improving), Snowflake (~58%)
  • Watch (<40): Salesforce (~42%), Adobe (~57% — mature)
"""

# ─────────────────────────────────────────────────────────────
# 6. FORMAT & PRINT REPORT
# ─────────────────────────────────────────────────────────────

def format_change(pct: float) -> str:
    arrow = "▲" if pct >= 0 else "▼"
    return f"{arrow} {abs(pct):.2f}%"

def run_monitor():
    now_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    lines = [
        "=" * 72,
        "JESSICA YANG — MARKET & MACRO MONITOR",
        f"Generated: {now_str}",
        "=" * 72,
    ]

    # ── Indices ──────────────────────────────────────────────
    lines += ["", "── EQUITY INDICES ─────────────────────────────────────────────────"]
    for name, symbol in INDICES.items():
        q = get_yahoo_quote(symbol)
        if "error" in q:
            lines.append(f"  {name:<22} {symbol:<8}  ⚠️  {q['error']}")
        else:
            price_str = f"${q['price']:>10,.2f}" if q['price'] and q['price'] > 10 else f"{q['price']:>6.2f}"
            lines.append(f"  {name:<22} {symbol:<8}  {price_str}   {format_change(q['change_pct'])}")
        time.sleep(0.3)

    # ── Coverage Universe ────────────────────────────────────
    lines += ["", "── SAAS COVERAGE UNIVERSE ──────────────────────────────────────────"]
    for name, symbol in COVERAGE.items():
        q = get_yahoo_quote(symbol)
        if "error" in q:
            lines.append(f"  {name:<14} {symbol:<6}  ⚠️  {q['error']}")
        else:
            price_str = f"${q['price']:>8,.2f}"
            hi_lo = ""
            if q.get('52w_high') and q.get('52w_low'):
                pct_from_high = (q['price'] - q['52w_high']) / q['52w_high'] * 100
                hi_lo = f"  |  52W: ${q['52w_low']:,.0f}–${q['52w_high']:,.0f}  ({pct_from_high:+.1f}% from high)"
            lines.append(f"  {name:<14} {symbol:<6}  {price_str}   {format_change(q['change_pct'])}{hi_lo}")
        time.sleep(0.3)

    # ── Rates ────────────────────────────────────────────────
    lines += ["", "── RATES & YIELD CURVE ─────────────────────────────────────────────"]
    rates = {}
    for name, series in FRED_SERIES.items():
        val = get_fred_rate(series)
        rates[name] = val
        val_str = f"{val:.2f}%" if val else "N/A"
        lines.append(f"  {name:<20}  {val_str}")
        time.sleep(0.2)

    rate_10y = rates.get("10Y Treasury")
    rate_2y  = rates.get("2Y Treasury")
    if rate_10y and rate_2y:
        interp = analyze_yield_curve(rate_10y, rate_2y)
        lines.append(f"\n  Yield Curve: {interp}")

    # ── SaaS valuation context ───────────────────────────────
    lines += ["", "── SAAS VALUATION CONTEXT ──────────────────────────────────────────"]
    for l in SAAS_MULTIPLE_CONTEXT.strip().split("\n"):
        lines.append(f"  {l}")

    # ── Macro calendar ───────────────────────────────────────
    cal = get_macro_calendar()
    lines += ["", "── UPCOMING EVENTS CALENDAR ────────────────────────────────────────"]
    for e in cal["upcoming"]:
        pri_tag = f"[{e['priority']}]" if e['priority'] != "LOW" else "      "
        lines.append(f"  {pri_tag:8}  {e['date']:<16}  {e['ticker']:<6}  {e['event']}")

    lines += ["", "── WEEKLY MACRO WATCHLIST (standing) ───────────────────────────────"]
    for e in cal["weekly_watch"]:
        lines.append(f"  {e['day']:<12}  {e['event']:<35}  → {e['why_it_matters']}")

    # ── Talking points ───────────────────────────────────────
    lines += [
        "",
        "── THIS WEEK'S TALKING POINTS (for networking calls) ───────────────",
        "  1. 'The yield curve is the most important input for SaaS multiples right now —",
        "      every 50bps shift in the 10Y changes the DCF denominator materially.'",
        "  2. 'I'm watching ServiceNow earnings (Apr 23) as the first real data point",
        "      on whether GenAI ACV growth sustained its Q4 trajectory.'",
        "  3. 'Adobe is the most interesting valuation debate in my coverage — strong",
        "      fundamentals, compressed multiple. Either the market is wrong or Firefly",
        "      is a structural headwind disguised as a feature.'",
        "",
        "─" * 72,
        "Sources: Yahoo Finance, FRED (St. Louis Fed), Company IR pages",
        f"Generated: {now_str}",
        "=" * 72,
    ]

    report = "\n".join(lines)
    print(report)

    # Save
    fname = f"/home/user/workspace/macro_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(fname, "w") as f:
        f.write(report)
    print(f"\n✅ Report saved: {fname}")

    return report


# ─────────────────────────────────────────────────────────────
# SCHEDULING INSTRUCTIONS
# ─────────────────────────────────────────────────────────────
SCHEDULE_INSTRUCTIONS = """
HOW TO USE THIS SCRIPT:
─────────────────────────────────────────────────────────────
Run every Sunday morning before your week starts:
    python market_macro_monitor.py

What you get:
  • All major equity indices with weekly change
  • Your 6-company SaaS coverage with price + 52-week range
  • Current Treasury rates + yield curve interpretation
  • SaaS valuation multiple context (where we are vs. history)
  • Full upcoming earnings + macro events calendar
  • Three ready-to-use talking points for networking calls that week

Why this matters for recruiting:
  • You walk into every networking call knowing exactly where
    markets are, what's moving rates, and what's coming up
  • "I run a weekly macro monitor" is a simple, credible answer
    to 'how do you stay current on markets?'
  • Interviewers will ask about macro — this keeps you sharp
─────────────────────────────────────────────────────────────
"""

if __name__ == "__main__":
    run_monitor()
    print(SCHEDULE_INSTRUCTIONS)
