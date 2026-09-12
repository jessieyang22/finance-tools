# Options pricing and hedge sensitivities

## Research question

Can a transparent European pricing engine reconstruct observed SPXW option quotes, interpolate volatility smiles, and size local risk hedges? This is a pricing and risk study. There is only one archived quote snapshot, so historical hedge performance is unavailable.

## Contracts and timestamps

Source: [Cboe delayed SPX quotes](https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json). [Cboe SPX specifications](https://www.cboe.com/tradable-products/sp-500/spx-options/spx-specifications) document the $100 multiplier and distinguish SPXW expiration trading from standard SPX. Only SPXW is used, avoiding standard AM settlement. Expiry is assumed 16:00 America/New_York, ACT/365 elapsed seconds; selected dates are October 16, November 6, December 18 and December 31, 2026. The source timestamp is offset-free, so its New York interpretation is an explicit assumption. Per-contract quote timestamps are unavailable; last-trade timestamps are not quote timestamps. This is a delayed, possibly asynchronous snapshot. The index last trade is from the previous day and is used only to select the strike neighborhood.

## Data selection

Archive the whole response, then retain all SPXW contracts 30–120 calendar days from the snapshot. Select expiries nearest 35, 60, 90 and 115 days. Require positive bids, non-crossed quotes, positive bid/ask sizes, relative spread at most 35%, and strikes within 85–115% of the source index level. Open interest is preserved but is not an inclusion rule. Each excluded in-scope row has a reason; no imputation is performed. Use OTM puts below the inferred forward and calls at/above it to avoid double counting each strike.

## Forwards and rates

Choose the latest Treasury date strictly before the snapshot date. Interpolate published short-maturity par yields and use r = 2 log(1 + y/2) as an approximate continuously compounded financing proxy. Treasury par yields are not an OIS discount curve; this simplification is explicit. Infer F = median[K + (call midpoint − put midpoint)/D] from paired strikes within 3% of the source index level, D = exp(−rT). At least five pairs are required. Preserve each paired executable-price interval and report its consistency with F. The median is a robust estimate, not a simultaneous no-arbitrage fit.

## Pricing and units

Black-76 values a European payoff from the inferred forward. The CRR implementation evolves that forward with risk-neutral probability (1−d)/(u−d), then discounts the terminal payoff. The two methods are checked independently at increasing lattice sizes using actual contracts and calibrated IVs. The lattice is a numerical integration method; its nodes are model states, never fabricated historical observations.

Prices are index points. Forward delta and gamma differentiate with respect to F. Vega is per +1 volatility percentage point; theta is per day elapsed; rho is per +1 basis point with F fixed. These are conditional sensitivities. Rho therefore excludes changes in the forward or dividend assumptions, and forward delta is not an ETF share hedge ratio. Dollar option values multiply by 100. Solver repricing accuracy is an inversion check, not forecasting skill.

## Smile and hedge analysis

Fit a quadratic in log-moneyness to total implied variance separately for each expiry. Every fifth strike is held out deterministically. Report held-out price RMSE and fraction inside observed spreads. This evaluates cross-sectional interpolation, not future prediction. The simple quadratic is not guaranteed arbitrage-free; raw midpoint monotonicity/convexity diagnostics and negative fitted-variance counts are saved. Poor spread coverage must not be presented as a successful trading model.

For each expiry, take the nearest-forward accepted contract as a one-contract target. Choose observed put/call hedges near 97%/103% of the forward. Solve a two-by-two system to cancel forward delta and parallel-volatility vega. Preserve residual gamma. The sizing is fractional and theoretical; real contracts require integers and additional residual-risk controls. Entry spread costs use ask for buys and bid for sells, with no claim those delayed quotes were executable. Commission, market impact, margin, assignment/settlement processing, and future P&L are outside this snapshot study.

## Reproduce

From repository root: `python -m strats.options_pricing`. Inspect the report and CSVs under `strats/reports/options-pricing/`. To record another real snapshot, run `python -m strats.ingest --download` explicitly; content-addressed old raw files remain. A defensible future hedge backtest needs a matched contract history, contemporaneous hedge quotes, financing, actual trade costs, and settlement observations. Do not interpolate a missing historical options tape.
