# Options pricing and Treasury risk research

Two runnable quantitative-finance projects built on archived, traceable real market and government data. Python 3.11+ recommended.

| Project | Question | Open report |
|---|---|---|
| Options pricing and hedge sensitivities | How do actual SPXW quotes translate into implied volatility, Greeks and local hedge positions? | [Options report](reports/options-pricing/README.md) |
| Treasury curve and bond risk | How do actual Treasury notes respond to observed historical yield-curve changes? | [Treasury report](reports/treasury-risk/README.md) |

## Run from the repository root

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r strats/requirements.txt
python -m strats.ingest
python -m strats.options_pricing
python -m strats.treasury_risk
python -m unittest discover -s strats/tests -v
```

On Windows activate with `.venv\Scripts\activate` instead. All analysis runs offline against the archived responses. `python -m strats.ingest --download` explicitly refreshes real data; it never creates substitute observations if a source fails.

## What is included

- Observed Cboe bids/asks, quote rejection audit, parity-derived forwards, IV inversion, forward Greeks, CRR convergence, held-out-strike smile validation, and option-only delta/vega hedge sizing with observed spread costs.
- Official Treasury curves, actual note cash flows, independent auction-price validation, curve bootstrapping, clean/dirty pricing, DV01, key-rate risk, convexity, hedge positions and full repricing under dated historical curve changes.
- Raw source archives, cryptographic provenance, normalized inputs, reproducible CSV outputs, charts, numerical tests and GitHub Actions validation.

## Scope of conclusions

The options archive has one snapshot. It supports pricing and local risk analysis, not historical hedging returns. Its simple smile fit has limited held-out bid/ask coverage, which is reported directly. Treasury hedge distributions are fixed-date model repricing under historical shocks, not realized trading returns. The key-rate least-squares hedge is intentionally retained even though it performs worse than the simple DV01 hedge in this sample.

Read [options methodology](docs/OPTIONS.md), [Treasury methodology](docs/TREASURY.md), and [data provenance](docs/DATA.md). These projects have separate report folders and share source ingestion and numerical utilities. They do not depend on or validate older scripts elsewhere in this repository.
