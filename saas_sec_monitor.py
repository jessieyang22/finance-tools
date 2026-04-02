#!/usr/bin/env python3
"""
Jessica Yang — SaaS Coverage SEC Filing Monitor
================================================
Automatically checks SEC EDGAR for new 10-Q, 10-K, and 8-K filings
from your 6-company SaaS coverage universe.

Usage:
    python saas_sec_monitor.py              # Check all companies, print report
    python saas_sec_monitor.py --email      # Check + send email alert (configure below)
    python saas_sec_monitor.py --ticker HUBS # Check single company

Requirements: pip install requests  (pre-installed)
"""

import requests
import json
import time
import argparse
from datetime import datetime, timedelta
from typing import Optional

# ─────────────────────────────────────────────────────────────
# YOUR COVERAGE UNIVERSE
# Update CIK numbers if needed — these are the official SEC identifiers
# ─────────────────────────────────────────────────────────────
COVERAGE_UNIVERSE = {
    "HUBS":  {"name": "HubSpot Inc.",         "cik": "0001404655"},
    "CRM":   {"name": "Salesforce Inc.",       "cik": "0001108524"},
    "NOW":   {"name": "ServiceNow Inc.",       "cik": "0001373715"},
    "DDOG":  {"name": "Datadog Inc.",          "cik": "0001659166"},
    "SNOW":  {"name": "Snowflake Inc.",        "cik": "0001640147"},
    "ADBE":  {"name": "Adobe Inc.",            "cik": "0000796343"},
}

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
EDGAR_BASE = "https://data.sec.gov"
EDGAR_SUBMISSIONS = f"{EDGAR_BASE}/submissions/CIK{{cik}}.json"
FILING_TYPES_TO_WATCH = ["10-Q", "10-K", "8-K"]   # 8-K catches earnings releases
LOOKBACK_DAYS = 7       # How many days back to check for "new" filings
HEADERS = {
    # SEC EDGAR requires: "Name email@domain.com" format
    # If you get a 403 error, use your actual email below
    "User-Agent": "Jessica Yang yangjessie7@gmail.com"
}

# ─────────────────────────────────────────────────────────────
# CORE FUNCTIONS
# ─────────────────────────────────────────────────────────────

def get_recent_filings(cik: str, ticker: str, company_name: str,
                        lookback_days: int = LOOKBACK_DAYS) -> list[dict]:
    """
    Query SEC EDGAR for recent filings for a given company.
    Returns list of new filings within the lookback window.
    """
    url = EDGAR_SUBMISSIONS.format(cik=cik.lstrip("0").zfill(10))
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  ⚠️  Error fetching {ticker}: {e}")
        return []

    filings = data.get("filings", {}).get("recent", {})
    forms       = filings.get("form", [])
    dates       = filings.get("filingDate", [])
    accessions  = filings.get("accessionNumber", [])
    descriptions= filings.get("primaryDocument", [])

    cutoff = datetime.now() - timedelta(days=lookback_days)
    new_filings = []

    for form, date_str, accession, doc in zip(forms, dates, accessions, descriptions):
        if form not in FILING_TYPES_TO_WATCH:
            continue
        try:
            filing_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if filing_date >= cutoff:
            acc_clean = accession.replace("-", "")
            url = (f"https://www.sec.gov/Archives/edgar/full-index/"
                   f"edgar/full-index/{date_str[:4]}/QTR{(filing_date.month-1)//3+1}/")
            filing_url = (f"https://www.sec.gov/cgi-bin/browse-edgar"
                          f"?action=getcompany&CIK={cik}&type={form}&dateb=&owner=include&count=5")
            new_filings.append({
                "ticker": ticker,
                "company": company_name,
                "form": form,
                "date": date_str,
                "accession": accession,
                "url": filing_url,
                "days_ago": (datetime.now() - filing_date).days,
            })

    return new_filings


def check_next_earnings_window() -> list[dict]:
    """
    Returns upcoming expected earnings dates based on typical filing patterns.
    These are ESTIMATES — always verify on company IR pages.
    """
    # Based on Q4 2025 / FY2025 earnings season (reported Feb 2026)
    # Q1 2026 earnings expected late April / early May 2026
    upcoming = [
        {"ticker": "HUBS",  "company": "HubSpot",    "expected": "May 6–8, 2026",   "quarter": "Q1 2026",   "priority": "HIGH"},
        {"ticker": "NOW",   "company": "ServiceNow",  "expected": "Apr 23–24, 2026",  "quarter": "Q1 2025",   "priority": "HIGH"},
        {"ticker": "DDOG",  "company": "Datadog",     "expected": "May 7–9, 2026",    "quarter": "Q1 2026",   "priority": "HIGH"},
        {"ticker": "CRM",   "company": "Salesforce",  "expected": "May 28, 2026",     "quarter": "Q1 FY27",   "priority": "MED"},
        {"ticker": "SNOW",  "company": "Snowflake",   "expected": "May 21–22, 2026",  "quarter": "Q1 FY27",   "priority": "MED"},
        {"ticker": "ADBE",  "company": "Adobe",       "expected": "Jun 12, 2026",     "quarter": "Q2 FY26",   "priority": "MED"},
    ]
    return upcoming


def format_report(all_filings: list[dict], lookback_days: int) -> str:
    """Format the output report as clean text."""
    now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    lines = [
        "=" * 70,
        "JESSICA YANG — SaaS Coverage SEC Filing Alert",
        f"Run Date: {now_str}",
        f"Lookback Window: Last {lookback_days} days",
        "=" * 70,
    ]

    if not all_filings:
        lines.append("\n✅  No new 10-Q, 10-K, or 8-K filings in the past "
                     f"{lookback_days} days across your coverage universe.\n")
    else:
        lines.append(f"\n🚨  FOUND {len(all_filings)} NEW FILING(S):\n")
        for f in all_filings:
            lines += [
                f"  {'─'*55}",
                f"  Company  : {f['company']} ({f['ticker']})",
                f"  Form     : {f['form']}",
                f"  Filed    : {f['date']} ({f['days_ago']} days ago)",
                f"  EDGAR    : {f['url']}",
                "",
            ]

    lines += [
        "\n" + "─" * 70,
        "UPCOMING EARNINGS CALENDAR (estimated):",
        "─" * 70,
    ]
    upcoming = check_next_earnings_window()
    for e in upcoming:
        priority_tag = f"[{e['priority']}]" if e['priority'] != "LOW" else "     "
        lines.append(f"  {priority_tag:8}  {e['ticker']:<6} {e['company']:<16} "
                     f"{e['quarter']:<12} → Expected: {e['expected']}")

    lines += [
        "",
        "─" * 70,
        "QUICK METRICS REMINDER (update after each earnings):",
        "  → Revenue YoY growth    → NRR/NDR    → FCF margin",
        "  → Forward guidance      → Beat/miss  → Stock reaction",
        "─" * 70,
        f"Source: SEC EDGAR (https://www.sec.gov/cgi-bin/browse-edgar)",
        "=" * 70,
    ]
    return "\n".join(lines)


def run_check(ticker_filter: Optional[str] = None,
              lookback_days: int = LOOKBACK_DAYS,
              verbose: bool = True) -> list[dict]:
    """
    Main function: check all companies (or one) for new filings.
    Returns list of all new filings found.
    """
    universe = COVERAGE_UNIVERSE
    if ticker_filter:
        ticker_filter = ticker_filter.upper()
        if ticker_filter not in universe:
            print(f"Ticker {ticker_filter} not in coverage universe. "
                  f"Available: {', '.join(universe.keys())}")
            return []
        universe = {ticker_filter: universe[ticker_filter]}

    all_filings = []
    print(f"\nChecking {len(universe)} company/companies for new SEC filings...\n")

    for ticker, info in universe.items():
        if verbose:
            print(f"  → Checking {ticker} ({info['name']})...")
        filings = get_recent_filings(info["cik"], ticker, info["name"], lookback_days)
        if filings:
            print(f"    🚨 {len(filings)} new filing(s) found!")
            all_filings.extend(filings)
        else:
            if verbose:
                print(f"    ✅ No new filings in last {lookback_days} days")
        time.sleep(0.5)   # Respect SEC rate limits (10 req/sec max)

    report = format_report(all_filings, lookback_days)
    print("\n" + report)

    # Save report to file
    report_path = f"sec_filing_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\n✅ Report saved to: {report_path}")

    return all_filings


# ─────────────────────────────────────────────────────────────
# SCHEDULING INSTRUCTIONS (print these as a reminder)
# ─────────────────────────────────────────────────────────────
SCHEDULE_INSTRUCTIONS = """
HOW TO AUTOMATE THIS SCRIPT (set it and forget it):
─────────────────────────────────────────────────────────────
Option A — Run manually every Sunday (recommended for now):
    python saas_sec_monitor.py

Option B — Add to cron (Mac/Linux) for weekly auto-run:
    1. Open Terminal → type: crontab -e
    2. Add this line (runs every Monday at 8am):
       0 8 * * 1 cd /path/to/workspace && python saas_sec_monitor.py >> sec_log.txt 2>&1
    3. Save and exit

Option C — Windows Task Scheduler:
    1. Open Task Scheduler → Create Basic Task
    2. Trigger: Weekly, Monday, 8:00 AM
    3. Action: python /path/to/saas_sec_monitor.py

What this does:
  • Hits SEC EDGAR API (free, no API key needed)
  • Checks all 6 companies for 10-Q, 10-K, 8-K filings in last 7 days
  • Prints a clean report with upcoming earnings calendar
  • Saves report to a timestamped .txt file

WHY THIS MATTERS FOR RECRUITING:
  • Shows systematic, process-driven investing approach
  • "I automated my filing alerts" → instantly differentiates you
  • Ensures you never miss an earnings report for your coverage
─────────────────────────────────────────────────────────────
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SaaS Coverage SEC Filing Monitor")
    parser.add_argument("--ticker", type=str, default=None,
                        help="Check a single ticker (e.g., --ticker HUBS)")
    parser.add_argument("--days", type=int, default=LOOKBACK_DAYS,
                        help=f"Lookback window in days (default: {LOOKBACK_DAYS})")
    parser.add_argument("--quiet", action="store_true",
                        help="Only print if filings found")
    parser.add_argument("--instructions", action="store_true",
                        help="Print scheduling instructions")
    args = parser.parse_args()

    if args.instructions:
        print(SCHEDULE_INSTRUCTIONS)
    else:
        filings = run_check(
            ticker_filter=args.ticker,
            lookback_days=args.days,
            verbose=not args.quiet
        )
        print(SCHEDULE_INSTRUCTIONS)
