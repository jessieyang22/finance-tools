#!/usr/bin/env python3
"""
Jessica Yang — SaaS Coverage Monitor
======================================
Tracks a 6-company SaaS coverage universe: HUBS, CRM, NOW, DDOG, SNOW, ADBE.

Pulls live prices from Yahoo Finance (no API key required).
Fundamentals (NRR, margins, EV/NTM Rev) are hardcoded from the most recent
earnings releases and updated each quarter.

Run any time:
    python saas_coverage_monitor.py

Coverage started: September 2025
Last fundamentals update: Q4 2025 / FY2025 earnings
"""

import requests
import time
from datetime import datetime
from typing import Optional

HEADERS = {"User-Agent": "Jessica Yang yangjessie7@gmail.com"}

# ─────────────────────────────────────────────────────────────
# COVERAGE UNIVERSE
# Fundamentals updated from Q4 2025 / FY2025 earnings releases
# ─────────────────────────────────────────────────────────────

COVERAGE = [
    {
        "ticker":       "HUBS",
        "name":         "HubSpot",
        "view":         "BUY",
        "conviction":   4,          # out of 5
        # Fundamentals (Q4 2025)
        "ltm_rev":      3.13,       # LTM revenue $B
        "rev_growth":   19,         # YoY revenue growth %
        "nrr":          105,        # Net Revenue Retention %
        "gross_margin": 84,
        "fcf_margin":   19,
        "ev_ntm_rev":   9.0,        # EV / NTM Revenue multiple
        # Thesis
        "thesis":       "AI-native CRM leader in SMB upgrade cycle. Breeze AI agents embedded platform-wide. "
                        "Key Q1 question: does RPO inflect as usage-based pricing ramps?",
        "bull":         "289K customers, Breeze AI shipping, FY26 guide $3.69–3.70B (+18%)",
        "bear":         "NRR drifted 110% → 105%; Salesforce Agentforce competition intensifying",
        "watch":        "Q1 earnings May 6–8 — RPO growth and NRR floor",
        "next_earnings":"May 6–8, 2026",
    },
    {
        "ticker":       "CRM",
        "name":         "Salesforce",
        "view":         "HOLD",
        "conviction":   2,
        "ltm_rev":      37.9,
        "rev_growth":   9,
        "nrr":          110,
        "gross_margin": 77,
        "fcf_margin":   33,
        "ev_ntm_rev":   6.5,
        "thesis":       "Agentforce is credible — $900M+ pipeline, 5K+ deals. Bull case requires "
                        "consumption revenue to show up in FY26 numbers.",
        "bull":         "Agentforce + Data Cloud flywheel; FCF margin 33% = exceptional cash at scale",
        "bear":         "Only 9% growth on $37.9B base; Agentforce revenue not yet in reported metrics",
        "watch":        "FY27 guidance — does Agentforce drive re-acceleration above 10%?",
        "next_earnings":"May 28, 2026 (est.)",
    },
    {
        "ticker":       "NOW",
        "name":         "ServiceNow",
        "view":         "BUY",
        "conviction":   4,
        "ltm_rev":      10.98,
        "rev_growth":   22,
        "nrr":          99,         # 99% renewal rate
        "gross_margin": 80,
        "fcf_margin":   30,
        "ev_ntm_rev":   13.0,
        "thesis":       "Best enterprise AI monetization in SaaS. Now Assist 150%+ QoQ. "
                        "cRPO $10.3B gives unmatched forward revenue visibility.",
        "bull":         "Now Assist ACV growing 150%+ QoQ; cRPO $10.3B; 99% renewal rate",
        "bear":         "Multiple expensive at 13x — any growth decel compresses hard",
        "watch":        "Q1 earnings Apr 23–24 — cRPO growth and Now Assist deal count",
        "next_earnings":"Apr 23–24, 2026",
    },
    {
        "ticker":       "DDOG",
        "name":         "Datadog",
        "view":         "BUY",
        "conviction":   3,
        "ltm_rev":      2.68,
        "rev_growth":   26,
        "nrr":          120,
        "gross_margin": 81,
        "fcf_margin":   23,
        "ev_ntm_rev":   13.0,
        "thesis":       "Picks-and-shovels on AI infrastructure. Every AI workload needs "
                        "monitoring — Datadog dominates that layer. NRR 120% = strongest expansion engine.",
        "bull":         "NRR 120%; AI Observability = new TAM; 26% growth accelerating with AI infra spend",
        "bear":         "Hyperscalers may build in-house observability; LLM cost optimization risk",
        "watch":        "Q1 earnings May 7–9 — NRR stability and AI product bookings",
        "next_earnings":"May 7–9, 2026",
    },
    {
        "ticker":       "SNOW",
        "name":         "Snowflake",
        "view":         "WATCH",
        "conviction":   2,
        "ltm_rev":      3.44,
        "rev_growth":   29,
        "nrr":          131,
        "gross_margin": 70,
        "fcf_margin":   29,
        "ev_ntm_rev":   12.0,
        "thesis":       "Best NRR (131%) and fastest growth (29%) in the universe, but CEO transition "
                        "risk and Apache Iceberg interoperability may erode the proprietary moat.",
        "bull":         "NRR 131%; Cortex AI + Snowpark moving up the value chain",
        "bear":         "CEO transition; Iceberg reduces lock-in; lowest gross margin (70%) in universe",
        "watch":        "FY27 guidance and Cortex ARR disclosure — need evidence of platform stickiness",
        "next_earnings":"May 21, 2026 (est.)",
    },
    {
        "ticker":       "ADBE",
        "name":         "Adobe",
        "view":         "HOLD",
        "conviction":   2,
        "ltm_rev":      23.77,
        "rev_growth":   11,
        "nrr":          110,
        "gross_margin": 88,
        "fcf_margin":   43,
        "ev_ntm_rev":   6.5,
        "thesis":       "The paradox: best FCF margin (43%) and gross margin (88%) in the universe, "
                        "but faces structural risk from AI image generation commoditizing creative work.",
        "bull":         "FCF 43%; Firefly 16B+ images; AI-influenced ARR >$5B; gross margin 88%",
        "bear":         "Midjourney/DALL-E commoditizing from below; Figma blocked; only 11% growth",
        "watch":        "Firefly monetization rate — does it reach $2B ARR by FY26?",
        "next_earnings":"Jun 12, 2026 (est.)",
    },
]

# ─────────────────────────────────────────────────────────────
# LIVE DATA — Yahoo Finance (no API key)
# ─────────────────────────────────────────────────────────────

def get_live_quote(symbol: str) -> Optional[dict]:
    """Pull latest price, change %, and 52-week range from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": "1d", "range": "5d"}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        meta = resp.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose", 0)
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose", price)
        w52_high = meta.get("fiftyTwoWeekHigh")
        w52_low  = meta.get("fiftyTwoWeekLow")
        chg_pct  = ((price - prev) / prev * 100) if prev else 0
        from_high = ((price - w52_high) / w52_high * 100) if w52_high else None
        return {
            "price":      price,
            "change_pct": chg_pct,
            "52w_high":   w52_high,
            "52w_low":    w52_low,
            "from_high":  from_high,
        }
    except Exception as e:
        return {"error": str(e)}

# ─────────────────────────────────────────────────────────────
# CALCULATIONS
# ─────────────────────────────────────────────────────────────

def rule_of_40(co: dict) -> int:
    return co["rev_growth"] + co["fcf_margin"]

def rule_of_40_grade(score: int) -> str:
    if score >= 60: return "ELITE"
    if score >= 50: return "STRONG"
    if score >= 40: return "GOOD"
    return "WATCH"

def conviction_bar(n: int, total: int = 5) -> str:
    return "●" * n + "○" * (total - n)

def chg_arrow(pct: float) -> str:
    return f"▲ +{pct:.2f}%" if pct >= 0 else f"▼  {pct:.2f}%"

VIEW_COLORS = {"BUY": "BUY ▲", "HOLD": "HOLD →", "WATCH": "WATCH ▼"}

# ─────────────────────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────────────────────

def run():
    now_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    W = 78

    def line(char="─"): return char * W

    rows = []
    rows += [
        "=" * W,
        "JESSICA YANG — SAAS COVERAGE MONITOR",
        f"6-Company Universe: HUBS · CRM · NOW · DDOG · SNOW · ADBE",
        f"Generated: {now_str}",
        "Coverage started: September 2025  |  Fundamentals: Q4 2025 / FY2025 earnings",
        "=" * W,
    ]

    # ── 1. LIVE PRICE SNAPSHOT ───────────────────────────────
    rows += ["", line(), " LIVE PRICE SNAPSHOT", line()]
    rows.append(f"  {'TICKER':<7} {'NAME':<14} {'PRICE':>9} {'DAY CHG':>10}  {'52W RANGE':>22}  {'FROM HIGH':>10}  VIEW")
    rows.append(f"  {'-'*7} {'-'*14} {'-'*9} {'-'*10}  {'-'*22}  {'-'*10}  {'-'*8}")

    quotes = {}
    for co in COVERAGE:
        q = get_live_quote(co["ticker"])
        quotes[co["ticker"]] = q
        time.sleep(0.3)

        if "error" in q:
            rows.append(f"  {co['ticker']:<7} {co['name']:<14}  ⚠  {q['error']}")
            continue

        price_str   = f"${q['price']:>8,.2f}"
        chg_str     = chg_arrow(q["change_pct"])
        w52_str     = f"${q['52w_low']:,.0f}–${q['52w_high']:,.0f}" if q["52w_high"] else "N/A"
        high_str    = f"{q['from_high']:+.1f}%" if q["from_high"] is not None else "N/A"
        view_str    = co["view"]
        rows.append(f"  {co['ticker']:<7} {co['name']:<14} {price_str} {chg_str:>10}  {w52_str:>22}  {high_str:>10}  {view_str}")

    # ── 2. FUNDAMENTALS TABLE ────────────────────────────────
    rows += ["", line(), " FUNDAMENTALS  (as of Q4 2025 / FY2025 earnings)", line()]
    rows.append(f"  {'TICKER':<7} {'LTM REV':>9} {'GROWTH':>7} {'NRR':>6} {'GM':>5} {'FCF':>5} {'EV/NTM':>7} {'R40':>5} {'GRADE':<8} {'CONVICTION'}")
    rows.append(f"  {'-'*7} {'-'*9} {'-'*7} {'-'*6} {'-'*5} {'-'*5} {'-'*7} {'-'*5} {'-'*8} {'-'*14}")

    for co in COVERAGE:
        r40   = rule_of_40(co)
        grade = rule_of_40_grade(r40)
        rows.append(
            f"  {co['ticker']:<7} "
            f"${co['ltm_rev']:>6.2f}B "
            f"{co['rev_growth']:>5}%  "
            f"{co['nrr']:>4}%  "
            f"{co['gross_margin']:>3}%  "
            f"{co['fcf_margin']:>3}%  "
            f"{co['ev_ntm_rev']:>5.1f}x  "
            f"{r40:>3}   "
            f"{grade:<8} "
            f"{conviction_bar(co['conviction'])}"
        )

    # ── 3. UNIVERSE AVERAGES ─────────────────────────────────
    rows += ["", line(), " UNIVERSE AVERAGES", line()]
    avg_growth  = sum(c["rev_growth"]  for c in COVERAGE) / len(COVERAGE)
    avg_nrr     = sum(c["nrr"]        for c in COVERAGE) / len(COVERAGE)
    avg_gm      = sum(c["gross_margin"]for c in COVERAGE) / len(COVERAGE)
    avg_fcf     = sum(c["fcf_margin"]  for c in COVERAGE) / len(COVERAGE)
    avg_ev      = sum(c["ev_ntm_rev"]  for c in COVERAGE) / len(COVERAGE)
    avg_r40     = sum(rule_of_40(c)   for c in COVERAGE) / len(COVERAGE)
    buy_count   = sum(1 for c in COVERAGE if c["view"] == "BUY")
    hold_count  = sum(1 for c in COVERAGE if c["view"] == "HOLD")
    watch_count = sum(1 for c in COVERAGE if c["view"] == "WATCH")

    rows += [
        f"  Avg Revenue Growth : {avg_growth:.1f}%",
        f"  Avg NRR            : {avg_nrr:.0f}%",
        f"  Avg Gross Margin   : {avg_gm:.0f}%",
        f"  Avg FCF Margin     : {avg_fcf:.1f}%",
        f"  Avg EV / NTM Rev   : {avg_ev:.1f}x  (2021 peak ~20x · 2022 trough ~5x)",
        f"  Avg Rule of 40     : {avg_r40:.0f}",
        f"  Ratings            : {buy_count} BUY · {hold_count} HOLD · {watch_count} WATCH",
    ]

    # ── 4. THESIS TRACKER ────────────────────────────────────
    rows += ["", line(), " THESIS TRACKER", line()]
    for co in COVERAGE:
        view_tag = f"[{co['view']}]"
        rows += [
            f"",
            f"  {co['ticker']} — {co['name']}  {view_tag}  {conviction_bar(co['conviction'])}",
            f"  Thesis : {co['thesis']}",
            f"  Bull   : {co['bull']}",
            f"  Bear   : {co['bear']}",
            f"  Watch  : {co['watch']}",
            f"  Next ER: {co['next_earnings']}",
        ]

    # ── 5. UPCOMING EARNINGS CALENDAR ───────────────────────
    rows += ["", line(), " EARNINGS CALENDAR — Q1 2026 SEASON", line()]
    calendar = [
        ("Apr 23–24", "NOW",  "ServiceNow Q1 2026",          "HIGH", "Now Assist ACV · cRPO growth"),
        ("May 6–8",   "HUBS", "HubSpot Q1 2026",             "HIGH", "RPO inflection · NRR floor"),
        ("May 7–9",   "DDOG", "Datadog Q1 2026",             "HIGH", "NRR stability · AI product bookings"),
        ("May 21",    "SNOW", "Snowflake Q1 FY27",           "MED",  "Cortex AI ARR · gross margin"),
        ("May 28",    "CRM",  "Salesforce Q1 FY27",          "MED",  "Agentforce consumption revenue"),
        ("Jun 12",    "ADBE", "Adobe Q2 FY2026",             "MED",  "Firefly monetization rate"),
    ]
    rows.append(f"  {'DATE':<12} {'TICKER':<6} {'EVENT':<32} {'PRIORITY':<8} WHAT TO WATCH")
    rows.append(f"  {'-'*12} {'-'*6} {'-'*32} {'-'*8} {'-'*30}")
    for date, ticker, event, priority, watch in calendar:
        rows.append(f"  {date:<12} {ticker:<6} {event:<32} {priority:<8} {watch}")

    # ── 6. TALKING POINTS ────────────────────────────────────
    rows += [
        "",
        line(),
        " THIS WEEK'S TALKING POINTS (for networking calls / interviews)",
        line(),
        "  1. \"I track a 6-company SaaS coverage universe — ServiceNow earnings Apr 23 is the",
        "      first real data point on whether GenAI ACV growth sustained its Q4 trajectory.\"",
        "",
        "  2. \"The most interesting valuation debate in my coverage is Adobe — best FCF margin",
        "      (43%) and gross margins (88%) in the universe, but the market is pricing in",
        "      existential risk from AI image generation commoditizing the creative layer.\"",
        "",
        "  3. \"Datadog has the strongest NRR at 120% — every new AI workload is incremental",
        "      revenue for them. It's the picks-and-shovels play on AI infrastructure.\"",
        "",
        line(),
        " HOW TO USE THIS SCRIPT",
        line(),
        "  Run every Sunday before your week starts:",
        "      python saas_coverage_monitor.py",
        "",
        "  Update quarterly after earnings (search 'FUNDAMENTALS UPDATE' in this file).",
        "  Source: Yahoo Finance (live prices) + company IR pages (quarterly fundamentals).",
        "",
        "  GitHub: https://github.com/jessieyang22/saas-coverage-dashboard",
        "  Dashboard: https://www.perplexity.ai/computer/a/saas-coverage-dashboard-jessic-CalNlwptQwWKApDLT1E3vA",
        "=" * W,
        f"Generated: {now_str}",
        "=" * W,
    ]

    report = "\n".join(rows)
    print(report)

    fname = f"saas_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(fname, "w") as f:
        f.write(report)
    print(f"\n✅  Report saved to {fname}")

    return report


if __name__ == "__main__":
    run()
