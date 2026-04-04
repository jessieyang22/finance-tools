#!/usr/bin/env python3
"""
Jessica Yang — S&P 500 Momentum Factor Backtest
=================================================
Strategy: Classic 12-1 momentum (12-month return, skip last month).
  - At the start of each month, rank all S&P 500 stocks by their
    prior 12-month return (skipping the most recent month).
  - Go long the top decile (winners), short the bottom decile (losers).
  - Hold for one month, then rebalance.
  - Compare long-only momentum portfolio vs. S&P 500 buy-and-hold.

Data: Yahoo Finance (free, no API key).
Lookback: 5 years of monthly data by default.

Run:
    pip install pandas numpy matplotlib yfinance
    python momentum_backtest.py

Output:
    - Terminal: annualized return, Sharpe ratio, max drawdown, win rate
    - Chart: cumulative returns (momentum vs. S&P 500)
    - Saved: momentum_backtest_results.png

Background reading:
    Jegadeesh & Titman (1993) "Returns to Buying Winners and Selling Losers"
    — the original momentum paper. Strategy has held up out-of-sample for 30+ years.

Author: Jessica Yang | github.com/jessieyang22/finance-tools
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # headless rendering — no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from datetime import datetime, timedelta

# ── optional: yfinance for live data, pandas_datareader as fallback ──
try:
    import yfinance as yf
    HAVE_YF = True
except ImportError:
    HAVE_YF = False

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

LOOKBACK_YEARS   = 5          # Total backtest window
MOMENTUM_MONTHS  = 12         # Formation period (months)
SKIP_MONTHS      = 1          # Skip most recent month (standard)
TOP_DECILE       = 0.10       # Long top 10%
BOTTOM_DECILE    = 0.10       # Short bottom 10%
BENCHMARK        = "^GSPC"    # S&P 500

# S&P 500 sample — 50 liquid large-caps across sectors
# Using a representative cross-section rather than all 500
# (keeps runtime fast; methodology is identical at full scale)
SP500_SAMPLE = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "ORCL", "CRM", "ADBE", "NOW",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "SCHW", "AXP", "C", "USB",
    # Healthcare
    "UNH", "LLY", "JNJ", "ABBV", "MRK", "TMO", "ABT", "DHR", "AMGN", "MDT",
    # Consumer / Retail
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "COST", "LOW", "WMT",
    # Industrials / Energy / Other
    "CAT", "BA", "HON", "RTX", "XOM", "CVX", "NEE", "DUK", "PLD", "AMT",
]

# ─────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────

def fetch_prices(tickers: list, years: int) -> pd.DataFrame:
    """Download adjusted monthly closing prices via Yahoo Finance."""
    end   = datetime.today()
    start = end - timedelta(days=365 * years + 60)

    print(f"  Downloading {len(tickers)} tickers from Yahoo Finance...")

    if not HAVE_YF:
        print("  ERROR: yfinance not installed. Run: pip install yfinance")
        sys.exit(1)

    raw = yf.download(
        tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval="1mo",
        auto_adjust=True,
        progress=False,
    )

    # Handle multi-level columns
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]] if "Close" in raw.columns else raw

    # Drop columns with too many missing values (>20%)
    thresh = int(len(prices) * 0.80)
    prices = prices.dropna(axis=1, thresh=thresh)

    print(f"  {prices.shape[1]} tickers with sufficient data | "
          f"{len(prices)} monthly periods")
    return prices


def fetch_benchmark(years: int) -> pd.Series:
    """Download S&P 500 monthly returns."""
    end   = datetime.today()
    start = end - timedelta(days=365 * years + 60)
    raw   = yf.download(
        BENCHMARK,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval="1mo",
        auto_adjust=True,
        progress=False,
    )
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].squeeze()
    else:
        close = raw["Close"]
    return close.pct_change().dropna()

# ─────────────────────────────────────────────────────────────
# STRATEGY
# ─────────────────────────────────────────────────────────────

def compute_momentum_signal(prices: pd.DataFrame) -> pd.DataFrame:
    """
    12-1 momentum: return over [t-12, t-1], skipping the most recent month.
    Avoids short-term reversal contaminating the signal.
    """
    # Total return from t-12 to t-1
    lag_start = MOMENTUM_MONTHS + SKIP_MONTHS   # 13 months ago
    lag_end   = SKIP_MONTHS                     # 1 month ago

    signal = prices.shift(lag_end) / prices.shift(lag_start) - 1
    return signal


def run_backtest(prices: pd.DataFrame, benchmark_rets: pd.Series) -> dict:
    """
    Monthly rebalancing momentum strategy.
    Returns dict with performance metrics and return series.
    """
    monthly_rets = prices.pct_change()
    signal       = compute_momentum_signal(prices)

    # Align dates — need at least MOMENTUM_MONTHS + 2 periods of history
    start_idx = MOMENTUM_MONTHS + SKIP_MONTHS + 1
    dates     = prices.index[start_idx:]

    strat_rets   = []  # Long-short momentum
    long_rets    = []  # Long-only winners (more IB-friendly)

    for i, date in enumerate(dates):
        prev_date = prices.index[start_idx + i - 1]

        # Get signal at previous month-end (no lookahead)
        sig = signal.loc[prev_date].dropna()
        if len(sig) < 10:
            strat_rets.append(np.nan)
            long_rets.append(np.nan)
            continue

        n_stocks = len(sig)
        n_top    = max(1, int(n_stocks * TOP_DECILE))
        n_bot    = max(1, int(n_stocks * BOTTOM_DECILE))

        winners = sig.nlargest(n_top).index
        losers  = sig.nsmallest(n_bot).index

        # This month's returns
        if date not in monthly_rets.index:
            strat_rets.append(np.nan)
            long_rets.append(np.nan)
            continue

        month_r = monthly_rets.loc[date]

        long_ret  = month_r[winners].mean()
        short_ret = month_r[losers].mean()

        # Long-short: long winners, short losers (equal-weighted legs)
        ls_ret = 0.5 * long_ret - 0.5 * short_ret
        strat_rets.append(ls_ret)
        long_rets.append(long_ret)

    result_index = dates[:len(strat_rets)]
    strat_series = pd.Series(strat_rets, index=result_index, name="Long-Short Momentum").dropna()
    long_series  = pd.Series(long_rets,  index=result_index, name="Long-Only Momentum").dropna()

    # Align benchmark
    bench = benchmark_rets.reindex(strat_series.index).dropna()
    strat_aligned = strat_series.reindex(bench.index).dropna()
    long_aligned  = long_series.reindex(bench.index).dropna()

    return {
        "long_short": strat_aligned,
        "long_only":  long_aligned,
        "benchmark":  bench,
    }

# ─────────────────────────────────────────────────────────────
# PERFORMANCE METRICS
# ─────────────────────────────────────────────────────────────

def annualized_return(rets: pd.Series) -> float:
    total = (1 + rets).prod()
    n     = len(rets) / 12
    return total ** (1 / n) - 1 if n > 0 else np.nan


def annualized_vol(rets: pd.Series) -> float:
    return rets.std() * np.sqrt(12)


def sharpe_ratio(rets: pd.Series, rf: float = 0.043) -> float:
    """Risk-free rate ~4.3% (current 10Y Treasury)."""
    excess = annualized_return(rets) - rf
    vol    = annualized_vol(rets)
    return excess / vol if vol > 0 else np.nan


def max_drawdown(rets: pd.Series) -> float:
    cum    = (1 + rets).cumprod()
    peak   = cum.cummax()
    dd     = (cum - peak) / peak
    return dd.min()


def win_rate(rets: pd.Series) -> float:
    return (rets > 0).mean()


def print_metrics(name: str, rets: pd.Series):
    print(f"\n  {name}")
    print(f"    Annualized Return : {annualized_return(rets)*100:+.1f}%")
    print(f"    Annualized Vol    : {annualized_vol(rets)*100:.1f}%")
    print(f"    Sharpe Ratio      : {sharpe_ratio(rets):.2f}")
    print(f"    Max Drawdown      : {max_drawdown(rets)*100:.1f}%")
    print(f"    Win Rate (months) : {win_rate(rets)*100:.0f}%")
    print(f"    Periods           : {len(rets)} months")

# ─────────────────────────────────────────────────────────────
# CHART
# ─────────────────────────────────────────────────────────────

def plot_results(results: dict, save_path: str = "momentum_backtest_results.png"):
    ls   = results["long_short"]
    lo   = results["long_only"]
    bench= results["benchmark"]

    cum_ls    = (1 + ls).cumprod()
    cum_lo    = (1 + lo).cumprod()
    cum_bench = (1 + bench).cumprod()

    # ── style ──
    BG       = "#0d1117"
    SURFACE  = "#161c27"
    BORDER   = "#2a3347"
    TEXT     = "#c8d0e0"
    MUTED    = "#6b7898"
    TEAL     = "#20a8b5"
    PURPLE   = "#a855f7"
    GOLD     = "#fbbf24"

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.patch.set_facecolor(BG)
    fig.suptitle(
        "S&P 500 Momentum Factor Backtest  |  12-1 Formation, Monthly Rebalance",
        color=TEXT, fontsize=13, fontweight="bold", y=0.98
    )

    ax_styles = dict(facecolor=SURFACE, linewidth=0)
    tick_styles = dict(colors=MUTED, labelsize=9)

    def style_ax(ax):
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.spines[:].set_color(BORDER)
        ax.spines[:].set_linewidth(0.5)
        ax.xaxis.label.set_color(MUTED)
        ax.yaxis.label.set_color(MUTED)
        ax.title.set_color(TEXT)
        ax.grid(axis="y", color=BORDER, linewidth=0.5, linestyle="--", alpha=0.5)

    # ── Chart 1: Cumulative returns ──────────────────────────
    ax1 = axes[0, 0]
    ax1.plot(cum_ls.index,    cum_ls.values,    color=TEAL,   lw=1.8, label="Long-Short Momentum")
    ax1.plot(cum_lo.index,    cum_lo.values,    color=PURPLE, lw=1.8, label="Long-Only Momentum")
    ax1.plot(cum_bench.index, cum_bench.values, color=GOLD,   lw=1.4, linestyle="--", label="S&P 500")
    ax1.set_title("Cumulative Returns", fontsize=10, fontweight="bold", pad=8)
    ax1.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{x:.1f}x"))
    ax1.legend(fontsize=8, facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT)
    style_ax(ax1)

    # ── Chart 2: Rolling 12M Sharpe ─────────────────────────
    ax2 = axes[0, 1]
    roll_sharpe_ls    = ls.rolling(12).apply(lambda r: sharpe_ratio(r), raw=False)
    roll_sharpe_bench = bench.rolling(12).apply(lambda r: sharpe_ratio(r), raw=False)
    ax2.plot(roll_sharpe_ls.index,    roll_sharpe_ls.values,    color=TEAL, lw=1.6, label="Momentum")
    ax2.plot(roll_sharpe_bench.index, roll_sharpe_bench.values, color=GOLD, lw=1.2, linestyle="--", label="S&P 500")
    ax2.axhline(0, color=BORDER, lw=0.8)
    ax2.axhline(1, color=TEAL,   lw=0.5, linestyle=":", alpha=0.5)
    ax2.set_title("Rolling 12-Month Sharpe Ratio", fontsize=10, fontweight="bold", pad=8)
    ax2.legend(fontsize=8, facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT)
    style_ax(ax2)

    # ── Chart 3: Drawdown ────────────────────────────────────
    ax3 = axes[1, 0]
    dd_ls    = (cum_ls    / cum_ls.cummax()    - 1) * 100
    dd_bench = (cum_bench / cum_bench.cummax() - 1) * 100
    ax3.fill_between(dd_ls.index,    dd_ls.values,    0, color=TEAL, alpha=0.35, label="Momentum")
    ax3.fill_between(dd_bench.index, dd_bench.values, 0, color=GOLD, alpha=0.20, label="S&P 500")
    ax3.set_title("Drawdown (%)", fontsize=10, fontweight="bold", pad=8)
    ax3.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax3.legend(fontsize=8, facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT)
    style_ax(ax3)

    # ── Chart 4: Monthly return distribution ────────────────
    ax4 = axes[1, 1]
    ax4.hist(ls.values * 100,    bins=24, color=TEAL, alpha=0.65, label="Momentum", edgecolor="none")
    ax4.hist(bench.values * 100, bins=24, color=GOLD, alpha=0.35, label="S&P 500",  edgecolor="none")
    ax4.axvline(0, color=TEXT, lw=0.8, linestyle="--")
    ax4.set_title("Monthly Return Distribution (%)", fontsize=10, fontweight="bold", pad=8)
    ax4.xaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax4.legend(fontsize=8, facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT)
    style_ax(ax4)

    # ── footnote ────────────────────────────────────────────
    fig.text(
        0.5, 0.01,
        f"Universe: {len(SP500_SAMPLE)}-stock S&P 500 sample  |  "
        f"Formation: {MOMENTUM_MONTHS}-month return, skip {SKIP_MONTHS}m  |  "
        f"Rebalance: monthly  |  Long top {int(TOP_DECILE*100)}%, short bottom {int(BOTTOM_DECILE*100)}%  |  "
        f"Data: Yahoo Finance  |  Generated: {datetime.now().strftime('%b %d, %Y')}",
        ha="center", color=MUTED, fontsize=7.5
    )

    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=BG)
    print(f"\n  Chart saved → {save_path}")
    return fig


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    W = 66
    print("=" * W)
    print("JESSICA YANG — S&P 500 MOMENTUM FACTOR BACKTEST")
    print(f"12-1 Momentum | Monthly Rebalance | {LOOKBACK_YEARS}-Year Window")
    print(f"Universe: {len(SP500_SAMPLE)}-stock S&P 500 sample")
    print(f"Run date: {datetime.now().strftime('%B %d, %Y')}")
    print("=" * W)

    # ── 1. Fetch data ──────────────────────────────────────
    print("\n[1/4] Fetching price data...")
    prices    = fetch_prices(SP500_SAMPLE, LOOKBACK_YEARS)
    bench_rets= fetch_benchmark(LOOKBACK_YEARS)

    # ── 2. Run backtest ────────────────────────────────────
    print("\n[2/4] Running backtest...")
    results = run_backtest(prices, bench_rets)

    ls    = results["long_short"]
    lo    = results["long_only"]
    bench = results["benchmark"]

    # ── 3. Print metrics ───────────────────────────────────
    print("\n[3/4] Performance Summary")
    print("-" * W)
    print_metrics("Long-Short Momentum  (long winners, short losers)", ls)
    print_metrics("Long-Only Momentum   (long winners only)", lo)
    print_metrics("S&P 500 (Buy & Hold)", bench)

    # ── Alpha ──────────────────────────────────────────────
    alpha = annualized_return(ls) - annualized_return(bench)
    print(f"\n  Long-Short Alpha vs. S&P 500: {alpha*100:+.1f}% annualized")

    # Correlation with benchmark
    corr = ls.corr(bench)
    print(f"  Long-Short Correlation to S&P 500: {corr:.2f}")
    print(f"  (lower = more diversifying)")

    # ── 4. Chart ───────────────────────────────────────────
    print("\n[4/4] Generating charts...")
    plot_results(results)

    # ── What this means ────────────────────────────────────
    print("\n" + "=" * W)
    print(" WHAT THIS STRATEGY IS")
    print("=" * W)
    print("""
  12-1 Momentum (Jegadeesh & Titman, 1993):

  Each month, rank all stocks by their return over the past
  12 months (skipping the most recent month to avoid short-
  term reversal). Buy the top decile (winners), short the
  bottom decile (losers). Rebalance every month.

  Why it works: investor underreaction — prices take time to
  fully reflect new information. Winners keep winning (and
  losers keep losing) over a 3-12 month horizon before
  eventually mean-reverting.

  Limitations:
    - High turnover → transaction costs erode live returns
    - Crashes hard in sharp reversals (March 2009, March 2020)
    - Requires shorting → not directly applicable long-only
    - Sample here is 50 stocks; live funds use full S&P 500

  Further reading:
    Jegadeesh & Titman (1993) — original paper
    AQR "Facts, Myths, and Momentum Investing" (2014)
    Fama & French (1996) — momentum as the "exception" to
    their 3-factor model

  GitHub: https://github.com/jessieyang22/finance-tools
""")
    print("=" * W)


if __name__ == "__main__":
    main()
