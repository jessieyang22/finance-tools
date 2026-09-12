# Treasury curve construction and bond risk

## Sources and instruments

The [U.S. Treasury daily par-yield feed](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=2026&type=daily_treasury_yield_curve) supplies actual published 2024–2026 observations. [TreasuryDirect auction records](https://www.treasurydirect.gov/TA_WS/securities/search?format=json&type=Note&auctionDate=2025-08-01,2025-08-31) supply five actual fixed-rate note issues, including CUSIP, issue/dated/maturity dates, coupon, auction yield and price. No bond terms are generated. All prices calculated from a curve are labelled model valuations; indicative par rates are not transaction prices for these individual securities.

## Curve construction

Use complete 6-month, 1-, 2-, 3-, 5-, 7-, 10-, 20- and 30-year par curves. Missing complete-curve dates are excluded and reported, never filled. Interpolate par coupons linearly at semiannual nodes, then recursively solve D(n) = [1 − (c/2) × sum(previous discount factors)] / (1 + c/2). Include D(0)=1. Interpolate log discount factors between nodes. Below six months this implies the first-node constant zero rate; no extrapolation beyond 30 years is allowed. The six-month yield is approximated as a semiannual coupon-equivalent input.

This is a transparent educational approximation built from Treasury's already fitted indicative par curve. It is not a reconstruction of individual dealer quotes or Treasury's proprietary implementation. Interpolated discount factors and zero rates are explicitly model outputs. Positive discount factors and repricing at every observed par tenor are tested.

## Bond valuation and conventions

Semiannual coupon dates are anchored to actual maturity dates, preserving end-of-month dates. Face value is $100 for pricing; coupon percentages come directly from TreasuryDirect. Accrued interest uses actual days divided by actual days in the coupon period. Cash-flow discount times use ACT/365. Settlement is the latest curve observation date for this study. On a coupon date, the just-paid coupon is excluded and accrued interest resets to zero.

Payment dates are contractual, with no holiday/weekend payment delay adjustment. The selected notes have regular coupon schedules; odd first/last coupons, TIPS, floaters and callable bonds are not supported. The independent auction check uses published auction yields and semiannual fractional-period discounting; a tolerance of $0.0003 per $100 accommodates the small differences observed for the September 2 issues. Both computed and reported prices, and every residual, are retained rather than rounded away.

Dirty price is the sum of discounted remaining payments; clean price subtracts accrued interest. The independent auction yield-price comparison validates cash-flow construction against published prices. Current model prices should not be compared with auction prices from different dates as if they were contemporaneous market errors.

## Risk and hedges

Central +/-1bp bumps to continuously compounded zero rates produce DV01, parallel-zero duration and convexity. Nine triangular key-rate bump functions sum to one across the supported grid. Key DV01s therefore approximately sum to parallel DV01; finite-difference nonlinear residuals are tested.

A $1m face five-year issue is the research target. The parallel hedge shorts the actual ten-year issue to cancel DV01. A separate unweighted least-squares key-rate hedge uses the actual two- and ten-year issues to minimize squared residual bucket sensitivities. The latter has no parallel-neutrality constraint. It can leave substantial level exposure and perform worse than the simple DV01 hedge. Its poor result is retained, not tuned away. Positions are research sizing choices, not observed investor holdings.

## Historical shock analysis

Bootstrap each actual complete curve, compute consecutive observed zero-rate changes, and apply those changes to the latest curve at a fixed valuation date. Fully reprice the current fixed bond positions under every resulting curve. Each row records both source dates and the calendar gap, including weekends/holidays. These are 672 historical observed-curve-change scenarios, not 672 independent experiments or necessarily one-calendar-day moves.

The shocks are real observed changes; applying them to current holdings is a counterfactual risk calculation. No artificial random rate paths are used. The reported standard deviations and loss quantiles describe model repricing under this historical sample. They are not realized investment P&L or a validated future VaR forecast. Carry, coupon reinvestment, aging, repo financing, liquidity spreads, transaction costs, and execution are excluded. Historical data were downloaded in one current vintage and are not guaranteed unrevised publication vintages.

## Reproduce

From repository root: `python -m strats.treasury_risk`. Read `strats/reports/treasury-risk/README.md`, inspect the actual dates in the shock ledger, and follow each bond's cash flows in `cashflows.csv`.
