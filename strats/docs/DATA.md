# Data provenance and reproducibility

All empirical observations come from public source responses. `data/manifest.json` records exact source URLs, retrieval timestamps, uncompressed SHA-256 hashes, raw byte counts, and normalized-file hashes. Immutable gzip files use content-addressed filenames. The original Cboe response is retained in full, including quotes that fail filters. Treasury XML and the original TreasuryDirect JSON are also retained.

| Dataset | Provider | Observed content | Model-derived content |
|---|---|---|---|
| SPX options snapshot | Cboe delayed quote endpoint | Contract identifiers, bids/asks, sizes, source IVs/Greeks, timestamps | Our forward estimates, IVs, Greeks, fitted smiles and hedge sizing |
| Daily Treasury par rates | U.S. Treasury | Published maturity/yield observations | Bootstrapped discount factors and zero rates |
| Treasury note auction records | TreasuryDirect | Actual CUSIPs, coupons, dates, yields and auction prices | Current curve valuations and risk sensitivities |

Source-provided IVs, Greeks and theoretical prices are vendor model outputs, even though they appear in the raw quote response. Our calculations do not use them as observed prices or calibration truth. The observed calibration inputs are bids/asks; source model fields are preserved solely for auditability.

The initial build imported source files downloaded immediately beforehand; retrieval timestamps are recorded from those files' write times in UTC. New `--download` runs record completion times directly. Acquisition errors stop execution. No synthetic-data fallback, random generator, fabricated return series, or missing-price imputation exists in these projects.

Numerical lattices, finite-difference bumps, interpolation, hypothetical portfolio sizes, and historical-shock repricing are mathematical calculations. Their outputs are labelled as such and are never represented as observed prices, investor holdings, or executed trading returns.

## Frozen reproduction

Install `strats/requirements.txt`, run `python -m strats.ingest` to rebuild normalized files from the archived responses, run both analysis modules, then `python -m unittest discover -s strats/tests -v`. Normal reproduction requires no network or API keys. Explicit refresh uses `python -m strats.ingest --download`. Review changed data and reports before committing a refresh. Source URLs can change, and current snapshots cannot recover old historical quotes.

Data retain their providers' rights and terms; this repository does not grant a separate market-data license. See the provider links in the manifest for attribution. The reports describe research on the supplied snapshot and do not assert permission for commercial redistribution or a live data service.
