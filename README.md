# finance-tools

Python scripts I built to systematize my equity research process. No API keys required — all data from free public sources (Yahoo Finance, SEC EDGAR, FRED).

**Coverage universe:** HUBS · CRM · NOW · DDOG · SNOW · ADBE

---

## Scripts

### `saas_coverage_monitor.py` — Weekly SaaS coverage report
Pulls live prices and outputs a full coverage report: price snapshot, fundamentals table, Rule of 40 scoring, per-company thesis tracker, and earnings calendar.

```bash
python saas_coverage_monitor.py
```

**Output:**
```
══════════════════════════════════════════════════════════════════════════
JESSICA YANG — SAAS COVERAGE MONITOR
6-Company Universe: HUBS · CRM · NOW · DDOG · SNOW · ADBE
Generated: Wednesday, April 01, 2026 at 08:00 AM
══════════════════════════════════════════════════════════════════════════

── LIVE PRICE SNAPSHOT
  TICKER  NAME           PRICE     DAY CHG       52W RANGE     FROM HIGH  VIEW
  HUBS    HubSpot        $242.79   ▲ +1.98%      $207–$683       -64.4%   BUY
  CRM     Salesforce     $186.24   ▲ +2.35%      $175–$296       -37.1%   HOLD
  NOW     ServiceNow     $871.50   ▼  -0.44%     $726–$1128      -22.7%   BUY
  ...

── FUNDAMENTALS  (Q4 2025 / FY2025 earnings)
── UNIVERSE AVERAGES
── THESIS TRACKER
── EARNINGS CALENDAR
── TALKING POINTS
```

Auto-saves a timestamped `.txt` report. Run every Sunday before the week starts.

---

### `market_macro_monitor.py` — Weekly market & macro snapshot
Pulls equity indices, Treasury rates, VIX, yield curve interpretation, and upcoming macro calendar.

```bash
python market_macro_monitor.py
```

**Covers:**
- S&P 500, Nasdaq, Russell 2000 — live prices + week change
- 10Y / 2Y Treasury rates, yield curve spread + interpretation
- VIX
- SaaS / Tech sector context (BVP Cloud Index proxy)
- Upcoming FOMC dates and implied rate path
- Earnings this week across the coverage universe

Data sources: Yahoo Finance, FRED (St. Louis Fed), Finviz.

---

### `saas_sec_monitor.py` — SEC EDGAR filing alert
Checks SEC EDGAR for new 10-Q, 10-K, and 8-K filings from the coverage universe. Run weekly or before earnings season.

```bash
python saas_sec_monitor.py              # Check all 6 companies
python saas_sec_monitor.py --ticker NOW # Check a single ticker
python saas_sec_monitor.py --days 14    # Extend lookback window to 14 days
```

**Uses:** Official SEC EDGAR API (`data.sec.gov`) — free, no key needed. Respects rate limits (0.5s delay between requests as required by SEC).

---

### `momentum_backtest.py` — S&P 500 momentum factor backtest
Implements the classic **12-1 momentum strategy** (Jegadeesh & Titman, 1993): rank all stocks by their prior 12-month return (skipping the most recent month), go long the top decile, short the bottom decile, rebalance monthly.

```bash
pip install pandas numpy matplotlib yfinance
python momentum_backtest.py
```

**Output:**
```
Long-Only Momentum   → +23.8% annualized  (Sharpe 0.88)
S&P 500 Buy & Hold   → +12.3% annualized  (Sharpe 0.54)
Long-Short Alpha     → -12.0% vs. benchmark (short leg hurt in bull market)
```

Generates a 4-panel dark-mode chart: cumulative returns, rolling Sharpe, drawdown, and return distribution. Outputs `momentum_backtest_results.png`.

**Universe:** 50-stock S&P 500 cross-section | **Data:** Yahoo Finance (free) | **Window:** 5 years monthly

---

## Setup

```bash
pip install requests
```

That's it. All three scripts use only `requests` plus Python's standard library.

---

## Updating after earnings

Fundamentals in `saas_coverage_monitor.py` are hardcoded at the top of the file in the `COVERAGE` list. After each earnings release, update the relevant company's fields:

```python
{
    "ticker":       "HUBS",
    "ltm_rev":      3.13,      # Update to new LTM revenue
    "rev_growth":   19,        # Update to new YoY growth %
    "nrr":          105,       # Update NRR
    "fcf_margin":   19,        # Update FCF margin
    "ev_ntm_rev":   9.0,       # Update valuation multiple
    "thesis":       "...",     # Update thesis narrative
    ...
}
```

---

## Q1 2026 Earnings Calendar

| Date | Ticker | Event | Priority |
|------|--------|-------|----------|
| Apr 23–24 | NOW | ServiceNow Q1 2026 | HIGH |
| May 6–8 | HUBS | HubSpot Q1 2026 | HIGH |
| May 7–9 | DDOG | Datadog Q1 2026 | HIGH |
| May 21 | SNOW | Snowflake Q1 FY27 | MED |
| May 28 | CRM | Salesforce Q1 FY27 | MED |
| Jun 12 | ADBE | Adobe Q2 FY26 | MED |

---

*Jessica Yang · University of Florida, B.S. Statistics · Class of 2029*
*[linkedin.com/in/jessica-l-yang](https://www.linkedin.com/in/jessica-l-yang/)*
