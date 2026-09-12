# Validation record

The initial checked-in build passed 18 automated tests locally using the versions in `requirements-tested.txt`. The workflow is configured to rebuild both projects offline on GitHub Actions; a configured workflow is not evidence that a remote run has passed.

Checks cover raw-source SHA-256 integrity, normalized-file hashes, exact accepted bid/ask agreement with archived quotes, IV inversion, put-call parity, analytical Greeks against numerical differences, independent lattice convergence, local option hedge exposures and spread accounting, rate-date availability, quote-audit conservation, bootstrap repricing, bond cash flows and accrued interest, actual auction-price reconciliation, coupon-date handling, key-rate risk aggregation, exact historical-shock reproduction, parallel hedge neutrality, and invalid-input rejection.

The numerical test fixtures use actual contracts and official observations. Deliberately invalid function arguments and mathematical perturbations exercise validation and sensitivities; they do not enter empirical datasets or reported market histories.

## Results requiring care

- One options snapshot cannot validate historical hedge P&L. None is reported.
- Quadratic smile held-out price RMSE is approximately 1.6–2.0 index points across the four expiries; only approximately 13–25% of held-out prices fall within the observed bid/ask spread. This model is a transparent baseline with limited quote accuracy.
- A one-million-dollar-face target has historical-shock repricing standard deviation around $1,936 unhedged and $670 with the parallel-DV01 hedge. These are model scenario statistics, not realized returns.
- The unconstrained key-rate least-squares hedge retains about $327/bp of level exposure and has scenario standard deviation around $1,789. Minimizing unweighted bucket exposures is not the same objective as minimizing realized curve-move risk.
- The independent published-auction check has maximum error about $0.000205 per $100 face. Residuals are retained in the output.

Both generated charts were visually checked for readable labels, units, and legends. No performance metrics are fabricated or substituted for missing data.
