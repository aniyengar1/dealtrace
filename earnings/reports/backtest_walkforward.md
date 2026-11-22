# BACKTEST — quarterly guidance walk-forward

**Retrospective public-date reconstruction; not live predictions, calibration certification, or an as-recorded operational track record.**

73 companies; 546 eligible source-matched targets; **532 predictions**; 14 insufficient-history exclusions. All five methods are scored on the same targets.

| Method | Mean unscaled Brier (lower is better) |
|---|---|
| quarter-frequency-v1 | 0.4845219366 |
| quarter-frequency-laplace-v1 | 0.4774861365 |
| walk-forward-pooled-base-rate | 0.5016966940 |
| uniform | 0.6666666667 |
| always-above | 0.7593984962 |

Evaluated outcomes: below: 4 (0.8%); within: 198 (37.2%); above: 330 (62.0%).
Company-specific history: 108; pooled fallback: 424.

**Below guidance: 4/532 = 0.7519%; nominal 95% Wilson interval 0.2928%–1.9171%.** Misses occur in only three companies; this independent-trial interval is not cluster-adjusted. See company/sector counts and limitations below.


## Methodology and limits

The fixed cohort is the 63 scaling-audit companies with at least six source-matched quarters plus the original ten manual-history companies (all meet six). Rambus is excluded for insufficient consolidated-range history. This is a survivorship-selected cohort of guidance-givers, not the US stock universe. Selection uses today’s coverage; it is not a historically investable universe. Scaling source curation is agent-reviewed research, not completed owner review or production onboarding. All blocked source rows remain exclusions; no ninth quarter is added.

For target results day D, simulate D−14 at New York midnight, preserving the frozen D−15 guidance-selection upper bound. Target guidance was selected in the pinned source audit/manual history; no result-day revision is used. Every training quarter must end strictly before the target quarter and its outcome must be publicly available by the simulated timestamp. Availability is the next New York midnight after the latest result publication, release SEC filing and exact actual SEC filing (including Q4 parent availability). Later restatements cannot enter an earlier fold. Exact IDs, source hashes, availability times and selected historical IDs are in the companion JSON.

Both frozen Python implementations are called unchanged. With ≥6 available own eligible quarters, use own frequencies; otherwise require ≥12 pooled eligible observations across ≥2 companies. The pool contains only earlier and available quarters from this fixed backtest cohort, including the target company; it is larger than the ten-company live pool. The latest eight-quarter cap remains unchanged. In this fixed panel each company has at most eight total quarters, so omitting blocked labels cannot bring an older ninth quarter into a window.

Raw history uses count/N. Smoothed uses (count+1)/(N+3). First two probabilities use half-even rounding to24 decimal places and above receives the residual. Uniform uses the same normalization for one-third; always-above assigns above=1. Unscaled Brier is sum over three classes of (probability−outcome indicator)^2, range0..2. Scores and aggregates use Decimal. No log score, clipping, fitted parameters, or probability tuning is introduced.

Recording/review timestamps are not backdated: this diagnostic explicitly uses the frozen retrospective mode. Today’s labels, fiscal/calendar choices, source selections and basis reviews introduce curation hindsight; historical scheduled-date evidence was not reconstructed. Forecast timestamps are reconstructed from known result dates, not actual historical prediction events. Most cases use pooled fallback because eight quarters provide few six-own-quarter training folds. Overlapping training samples and company outcomes are dependent. Small company samples, heterogeneous pooled firms, acquisition changes, missing source rows, survivorship and guidance practice changes limit generalization. The calibration table is descriptive on this sample; it is not a fresh validation set or proof of predictive quality.

## Per-company breakdown

| Company | n | Own / pool | Below / within / above | Raw history | Smoothed | Pooled base rate | Uniform | Always above |
|---|---|---|---|---|---|---|---|---|
| ABNB | 8 | 2 / 6 | 0 / 1 / 7 | 0.271520 | 0.305690 | 0.328903 | 0.666667 | 0.250000 |
| ADBE | 7 | 2 / 5 | 0 / 0 / 7 | 0.218715 | 0.240183 | 0.301566 | 0.666667 | 0.000000 |
| ADI | 7 | 2 / 5 | 0 / 3 / 4 | 0.640176 | 0.613879 | 0.499767 | 0.666667 | 0.857143 |
| AEIS | 8 | 2 / 6 | 0 / 3 / 5 | 0.490128 | 0.503251 | 0.441064 | 0.666667 | 0.750000 |
| AKAM | 8 | 2 / 6 | 0 / 5 / 3 | 0.507235 | 0.510943 | 0.591399 | 0.666667 | 1.250000 |
| AMAT | 7 | 1 / 6 | 0 / 7 / 0 | 0.691889 | 0.687497 | 0.829453 | 0.666667 | 2.000000 |
| AMD | 8 | 2 / 6 | 0 / 2 / 6 | 0.458730 | 0.458907 | 0.479730 | 0.666667 | 0.500000 |
| AMPL | 8 | 2 / 6 | 0 / 2 / 6 | 0.381659 | 0.409010 | 0.414684 | 0.666667 | 0.500000 |
| AMZN | 8 | 2 / 6 | 0 / 2 / 6 | 0.540817 | 0.491267 | 0.484181 | 0.666667 | 0.500000 |
| APP | 7 | 1 / 6 | 0 / 1 / 6 | 0.288083 | 0.313312 | 0.307329 | 0.666667 | 0.285714 |
| APPN | 8 | 2 / 6 | 0 / 0 / 8 | 0.198058 | 0.221010 | 0.281176 | 0.666667 | 0.000000 |
| AVPT | 8 | 2 / 6 | 0 / 0 / 8 | 0.203714 | 0.226007 | 0.287727 | 0.666667 | 0.000000 |
| BL | 7 | 1 / 6 | 0 / 5 / 2 | 0.577737 | 0.589085 | 0.660043 | 0.666667 | 1.428571 |
| CNXC | 8 | 2 / 6 | 1 / 2 / 5 | 0.730018 | 0.624177 | 0.646345 | 0.666667 | 0.750000 |
| COHR | 8 | 2 / 6 | 0 / 6 / 2 | 0.487092 | 0.516477 | 0.633148 | 0.666667 | 1.500000 |
| CRM | 7 | 2 / 5 | 0 / 4 / 3 | 0.562603 | 0.559022 | 0.550460 | 0.666667 | 1.142857 |
| CRUS | 8 | 2 / 6 | 0 / 4 / 4 | 0.504326 | 0.491646 | 0.508810 | 0.666667 | 1.000000 |
| CRWD | 6 | 1 / 5 | 0 / 0 / 6 | 0.254626 | 0.269482 | 0.301436 | 0.666667 | 0.000000 |
| CTSH | 8 | 2 / 6 | 0 / 4 / 4 | 0.606153 | 0.563017 | 0.610637 | 0.666667 | 1.000000 |
| DIOD | 8 | 2 / 6 | 0 / 5 / 3 | 0.718673 | 0.683584 | 0.693494 | 0.666667 | 1.250000 |
| DOCN | 6 | 0 / 6 | 0 / 0 / 6 | 0.275291 | 0.281521 | 0.286588 | 0.666667 | 0.000000 |
| DOCS | 7 | 1 / 6 | 0 / 0 / 7 | 0.201272 | 0.221336 | 0.244798 | 0.666667 | 0.000000 |
| ENPH | 7 | 1 / 6 | 0 / 6 / 1 | 0.706812 | 0.691364 | 0.812136 | 0.666667 | 1.714286 |
| EPAM | 8 | 2 / 6 | 0 / 1 / 7 | 0.458816 | 0.402674 | 0.340863 | 0.666667 | 0.250000 |
| EW | 8 | 2 / 6 | 0 / 3 / 5 | 0.594966 | 0.577412 | 0.556425 | 0.666667 | 0.750000 |
| FFIV | 6 | 0 / 6 | 0 / 0 / 6 | 0.268829 | 0.272020 | 0.268829 | 0.666667 | 0.000000 |
| FIVN | 7 | 1 / 6 | 0 / 2 / 5 | 0.427991 | 0.445519 | 0.436970 | 0.666667 | 0.571429 |
| FORM | 7 | 1 / 6 | 0 / 3 / 4 | 0.642055 | 0.613987 | 0.609835 | 0.666667 | 0.857143 |
| FTNT | 8 | 2 / 6 | 0 / 4 / 4 | 0.525218 | 0.526848 | 0.515067 | 0.666667 | 1.000000 |
| GTLB | 6 | 1 / 5 | 0 / 0 / 6 | 0.262834 | 0.278031 | 0.309133 | 0.666667 | 0.000000 |
| HIMS | 8 | 2 / 6 | 0 / 4 / 4 | 0.534109 | 0.535428 | 0.529399 | 0.666667 | 1.000000 |
| HLIT | 6 | 0 / 6 | 0 / 1 / 5 | 0.366606 | 0.366122 | 0.366237 | 0.666667 | 0.333333 |
| ICHR | 6 | 0 / 6 | 0 / 6 / 0 | 0.803108 | 0.797759 | 0.803108 | 0.666667 | 2.000000 |
| INTC | 8 | 2 / 6 | 0 / 4 / 4 | 0.631659 | 0.603373 | 0.621508 | 0.666667 | 1.000000 |
| IOT | 7 | 2 / 5 | 0 / 0 / 7 | 0.214770 | 0.236863 | 0.299377 | 0.666667 | 0.000000 |
| IPGP | 8 | 2 / 6 | 0 / 5 / 3 | 0.608309 | 0.590357 | 0.697361 | 0.666667 | 1.250000 |
| KFRC | 8 | 2 / 6 | 0 / 6 / 2 | 0.802112 | 0.747370 | 0.743925 | 0.666667 | 1.500000 |
| KLAC | 8 | 2 / 6 | 0 / 8 / 0 | 0.687825 | 0.675304 | 0.885053 | 0.666667 | 2.000000 |
| LITE | 6 | 0 / 6 | 0 / 5 / 1 | 0.710813 | 0.709560 | 0.710932 | 0.666667 | 1.666667 |
| LRCX | 8 | 2 / 6 | 0 / 8 / 0 | 0.687825 | 0.675304 | 0.885133 | 0.666667 | 2.000000 |
| LSCC | 8 | 2 / 6 | 0 / 6 / 2 | 1.120520 | 0.976008 | 0.756725 | 0.666667 | 1.500000 |
| LULU | 7 | 2 / 5 | 2 / 0 / 5 | 0.611103 | 0.580614 | 0.651322 | 0.666667 | 0.571429 |
| MCHP | 7 | 1 / 6 | 0 / 3 / 4 | 0.642971 | 0.614839 | 0.608613 | 0.666667 | 0.857143 |
| MDB | 6 | 1 / 5 | 0 / 0 / 6 | 0.255979 | 0.271479 | 0.310473 | 0.666667 | 0.000000 |
| META | 8 | 2 / 6 | 0 / 2 / 6 | 0.429100 | 0.408237 | 0.367459 | 0.666667 | 0.500000 |
| MKSI | 6 | 0 / 6 | 0 / 3 / 3 | 0.551926 | 0.549333 | 0.551926 | 0.666667 | 1.000000 |
| MPWR | 8 | 2 / 6 | 0 / 1 / 7 | 0.256043 | 0.288828 | 0.313182 | 0.666667 | 0.250000 |
| MXL | 8 | 2 / 6 | 0 / 8 / 0 | 0.687825 | 0.675304 | 0.885133 | 0.666667 | 2.000000 |
| NTAP | 6 | 1 / 5 | 0 / 5 / 1 | 0.952407 | 0.849557 | 0.673579 | 0.666667 | 1.666667 |
| NTNX | 7 | 2 / 5 | 0 / 1 / 6 | 0.307929 | 0.341072 | 0.375882 | 0.666667 | 0.285714 |
| NVDA | 7 | 1 / 6 | 0 / 0 / 7 | 0.255055 | 0.268990 | 0.295345 | 0.666667 | 0.000000 |
| OKTA | 6 | 1 / 5 | 0 / 0 / 6 | 0.238747 | 0.253125 | 0.286919 | 0.666667 | 0.000000 |
| ON | 7 | 1 / 6 | 0 / 7 / 0 | 0.687988 | 0.693788 | 0.801249 | 0.666667 | 2.000000 |
| ONTO | 6 | 0 / 6 | 0 / 4 / 2 | 0.732889 | 0.695685 | 0.728732 | 0.666667 | 1.333333 |
| PCTY | 8 | 2 / 6 | 0 / 0 / 8 | 0.171628 | 0.196862 | 0.240814 | 0.666667 | 0.000000 |
| PD | 6 | 1 / 5 | 0 / 3 / 3 | 0.580143 | 0.582379 | 0.551284 | 0.666667 | 1.000000 |
| PINS | 8 | 2 / 6 | 1 / 2 / 5 | 0.539519 | 0.517135 | 0.538956 | 0.666667 | 0.750000 |
| PLTR | 8 | 2 / 6 | 0 / 0 / 8 | 0.171628 | 0.196862 | 0.240814 | 0.666667 | 0.000000 |
| PLXS | 8 | 2 / 6 | 0 / 5 / 3 | 0.921098 | 0.831100 | 0.689122 | 0.666667 | 1.250000 |
| POWI | 7 | 1 / 6 | 0 / 7 / 0 | 0.779932 | 0.758710 | 0.893193 | 0.666667 | 2.000000 |
| QLYS | 8 | 2 / 6 | 0 / 0 / 8 | 0.171628 | 0.196862 | 0.241008 | 0.666667 | 0.000000 |
| RDDT | 8 | 2 / 6 | 0 / 0 / 8 | 0.182151 | 0.207085 | 0.240814 | 0.666667 | 0.000000 |
| RNG | 8 | 2 / 6 | 0 / 3 / 5 | 0.515018 | 0.527214 | 0.478564 | 0.666667 | 0.750000 |
| RPD | 8 | 2 / 6 | 0 / 0 / 8 | 0.185978 | 0.210807 | 0.247968 | 0.666667 | 0.000000 |
| S | 7 | 2 / 5 | 0 / 1 / 6 | 0.508410 | 0.440403 | 0.369187 | 0.666667 | 0.285714 |
| SANM | 8 | 2 / 6 | 0 / 5 / 3 | 0.714920 | 0.679386 | 0.692217 | 0.666667 | 1.250000 |
| SEDG | 7 | 1 / 6 | 0 / 5 / 2 | 0.567421 | 0.581302 | 0.648320 | 0.666667 | 1.428571 |
| TASK | 6 | 0 / 6 | 0 / 0 / 6 | 0.275879 | 0.282551 | 0.296887 | 0.666667 | 0.000000 |
| TDOC | 6 | 0 / 6 | 0 / 5 / 1 | 0.694833 | 0.693523 | 0.692233 | 0.666667 | 1.666667 |
| TENB | 7 | 1 / 6 | 0 / 0 / 7 | 0.230176 | 0.243618 | 0.269385 | 0.666667 | 0.000000 |
| TTMI | 8 | 2 / 6 | 0 / 0 / 8 | 0.171628 | 0.196862 | 0.240761 | 0.666667 | 0.000000 |
| TWLO | 7 | 1 / 6 | 0 / 0 / 7 | 0.230837 | 0.244272 | 0.271251 | 0.666667 | 0.000000 |
| ZS | 7 | 2 / 5 | 0 / 0 / 7 | 0.216798 | 0.238776 | 0.303996 | 0.666667 | 0.000000 |

## Calibration — fixed bins, no fitting

Bins are left-inclusive/right-exclusive, except final bin includes1. Each class is evaluated separately; empty cells are omitted. Small cell counts should not be interpreted as reliable calibration estimates.

| Method | Class | Predicted bin | n | Mean predicted | Observed frequency |
|---|---|---|---|---|---|
| always-above | above | [0.9,1] | 532 | 1.000000 | 0.620301 |
| always-above | below | [0,0.1) | 532 | 0.000000 | 0.007519 |
| always-above | within | [0,0.1) | 532 | 0.000000 | 0.372180 |
| quarter-frequency-laplace-v1 | above | [0.1,0.2) | 11 | 0.108081 | 0.181818 |
| quarter-frequency-laplace-v1 | above | [0.2,0.3) | 5 | 0.213333 | 0.600000 |
| quarter-frequency-laplace-v1 | above | [0.3,0.4) | 10 | 0.320000 | 0.400000 |
| quarter-frequency-laplace-v1 | above | [0.4,0.5) | 15 | 0.435556 | 0.733333 |
| quarter-frequency-laplace-v1 | above | [0.5,0.6) | 53 | 0.559035 | 0.716981 |
| quarter-frequency-laplace-v1 | above | [0.6,0.7) | 368 | 0.628480 | 0.614130 |
| quarter-frequency-laplace-v1 | above | [0.7,0.8) | 59 | 0.760934 | 0.593220 |
| quarter-frequency-laplace-v1 | above | [0.8,0.9) | 11 | 0.800000 | 1.000000 |
| quarter-frequency-laplace-v1 | below | [0,0.1) | 424 | 0.013498 | 0.002358 |
| quarter-frequency-laplace-v1 | below | [0.1,0.2) | 106 | 0.106604 | 0.018868 |
| quarter-frequency-laplace-v1 | below | [0.2,0.3) | 2 | 0.211111 | 0.500000 |
| quarter-frequency-laplace-v1 | within | [0.1,0.2) | 65 | 0.140740 | 0.338462 |
| quarter-frequency-laplace-v1 | within | [0.2,0.3) | 18 | 0.226186 | 0.166667 |
| quarter-frequency-laplace-v1 | within | [0.3,0.4) | 373 | 0.363868 | 0.378016 |
| quarter-frequency-laplace-v1 | within | [0.4,0.5) | 47 | 0.420493 | 0.276596 |
| quarter-frequency-laplace-v1 | within | [0.5,0.6) | 9 | 0.537037 | 0.777778 |
| quarter-frequency-laplace-v1 | within | [0.6,0.7) | 7 | 0.628571 | 0.428571 |
| quarter-frequency-laplace-v1 | within | [0.7,0.8) | 10 | 0.762222 | 0.600000 |
| quarter-frequency-laplace-v1 | within | [0.8,0.9) | 3 | 0.800000 | 1.000000 |
| quarter-frequency-v1 | above | [0,0.1) | 11 | 0.000000 | 0.181818 |
| quarter-frequency-v1 | above | [0.1,0.2) | 5 | 0.157143 | 0.600000 |
| quarter-frequency-v1 | above | [0.2,0.3) | 4 | 0.285714 | 0.750000 |
| quarter-frequency-v1 | above | [0.3,0.4) | 6 | 0.333333 | 0.166667 |
| quarter-frequency-v1 | above | [0.4,0.5) | 3 | 0.428571 | 0.333333 |
| quarter-frequency-v1 | above | [0.5,0.6) | 47 | 0.557368 | 0.723404 |
| quarter-frequency-v1 | above | [0.6,0.7) | 367 | 0.632244 | 0.615804 |
| quarter-frequency-v1 | above | [0.7,0.8) | 11 | 0.729756 | 0.727273 |
| quarter-frequency-v1 | above | [0.8,0.9) | 46 | 0.852285 | 0.478261 |
| quarter-frequency-v1 | above | [0.9,1] | 32 | 1.000000 | 0.937500 |
| quarter-frequency-v1 | below | [0,0.1) | 530 | 0.001527 | 0.005660 |
| quarter-frequency-v1 | below | [0.1,0.2) | 2 | 0.154762 | 0.500000 |
| quarter-frequency-v1 | within | [0,0.1) | 34 | 0.000000 | 0.058824 |
| quarter-frequency-v1 | within | [0.1,0.2) | 44 | 0.147394 | 0.522727 |
| quarter-frequency-v1 | within | [0.2,0.3) | 11 | 0.270244 | 0.090909 |
| quarter-frequency-v1 | within | [0.3,0.4) | 367 | 0.365551 | 0.381471 |
| quarter-frequency-v1 | within | [0.4,0.5) | 35 | 0.422963 | 0.314286 |
| quarter-frequency-v1 | within | [0.5,0.6) | 15 | 0.514286 | 0.266667 |
| quarter-frequency-v1 | within | [0.6,0.7) | 6 | 0.666667 | 0.833333 |
| quarter-frequency-v1 | within | [0.7,0.8) | 4 | 0.714286 | 0.250000 |
| quarter-frequency-v1 | within | [0.8,0.9) | 5 | 0.842857 | 0.400000 |
| quarter-frequency-v1 | within | [0.9,1] | 11 | 1.000000 | 0.818182 |
| uniform | above | [0.3,0.4) | 532 | 0.333333 | 0.620301 |
| uniform | below | [0.3,0.4) | 532 | 0.333333 | 0.007519 |
| uniform | within | [0.3,0.4) | 532 | 0.333333 | 0.372180 |
| walk-forward-pooled-base-rate | above | [0.5,0.6) | 33 | 0.576767 | 0.848485 |
| walk-forward-pooled-base-rate | above | [0.6,0.7) | 462 | 0.629629 | 0.619048 |
| walk-forward-pooled-base-rate | above | [0.7,0.8) | 2 | 0.750000 | 0.500000 |
| walk-forward-pooled-base-rate | above | [0.8,0.9) | 35 | 0.856201 | 0.428571 |
| walk-forward-pooled-base-rate | below | [0,0.1) | 532 | 0.002314 | 0.007519 |
| walk-forward-pooled-base-rate | within | [0.1,0.2) | 35 | 0.143799 | 0.571429 |
| walk-forward-pooled-base-rate | within | [0.2,0.3) | 2 | 0.250000 | 0.500000 |
| walk-forward-pooled-base-rate | within | [0.3,0.4) | 462 | 0.367706 | 0.372294 |
| walk-forward-pooled-base-rate | within | [0.4,0.5) | 33 | 0.423233 | 0.151515 |

## Reproduce

```sh
.venv/bin/python -m earnings.backtest_walkforward
```

Outputs: `earnings/reports/backtest_walkforward.json`, this report and a separate `earnings/publication/backtest.json` summary. No database connection, history ingestion, live prediction, or score insert occurs. Re-running changes execution time but the pinned inputs and deterministic case results remain reproducible.

## Denominators and subgroups

The initial pool contains592 quarter slots (64 scaling issuers plus the original ten, eight each). Removing Rambus’s eight-quarter panel leaves584 slots across73 companies. Source/basis/timing exclusions remove38;546 source-matched targets remain. Fourteen early targets lack the frozen minimum history, leaving532 scored cases. The same532 cases are used for all five score comparisons.

| Population | Scored n | Raw history | Smoothed | Pooled base rate | Uniform | Always above |
|---|---|---|---|---|---|---|
| 64-company scaling audit | 467 | 0.4997912040 | 0.4918545315 | 0.5163678558 | 0.6666666667 | 0.8222698073 |
| original ten-company manual history | 65 | 0.3748181229 | 0.3742547449 | 0.3962900391 | 0.6666666667 | 0.3076923077 |

The lead-time follow-up identified a concrete historical schedule mismatch for Lumentum: November5 was announced, while results were published November2 with merger news. Simulating from the now-known actual release date does not reproduce an operator’s scheduled-date knowledge. This reinforces the retrospective timing caveat; no live record is reconstructed or relabelled.

## Walk-forward pooled base-rate comparison

The additional benchmark is always cross-company: at each target timestamp t it counts **all eligible source-matched company-quarters strictly publicly available before t**, including already-public own history. It never switches to company-specific rates and does not smooth. Unlike the frozen methods, it imposes no target fiscal-end restriction: a different company’s later fiscal quarter is usable if already public. The finite pinned panel has at most eight quarters per company. No unavailable or blocked observation enters; each prediction stores the exact pool IDs, counts and probabilities. Day-precision availability retains the same conservative next-New-York-midnight rule. Training observations may include early targets omitted from scoring for cold-start history, once their outcomes become public. There is no fitted use of all 532 target labels. All five methods use the identical scored target set.

Walk-forward pooled mean Brier **0.5016966940**. For comparison only, fitting one frequency vector to these same 532 scored outcomes yields **0.4766521567** in-sample; this uses future labels and is not a forecast benchmark. Small differences below are descriptive, without a claim of statistically significant improvement.

| Historical selection mode | n | Raw history | Smoothed | Pooled base rate | Uniform | Always above |
|---|---|---|---|---|---|---|
| company | 108 | 0.3950512304 | 0.3901554641 | 0.4736051011 | 0.6666666667 | 0.6851851852 |
| pooled | 424 | 0.5073116447 | 0.4997307417 | 0.5088520997 | 0.6666666667 | 0.7783018868 |

These subgroups are defined solely by the frozen methods’ own-history/fallback decision, not by the new benchmark. They differ in companies and time periods, so their scores do not isolate a causal benefit of company-specific history.

## Below-guidance outcomes — rare and concentrated

**4 / 532 = 0.7519%**. Nominal 95% Wilson binomial interval: **0.2928%–1.9171%**. This interval assumes independent Bernoulli trials; repeated company quarters and common macro conditions violate independence, so it is not a cluster-adjusted population guarantee. It also does not account for guidance-giver survivorship, source exclusions or agent curation. Zero observed misses in a company or sector does not imply zero miss risk.

The per-company table above gives all denominators and outcomes. The four misses are:

| Company with a below outcome | Below / scored | Rate |
|---|---|---|
| CNXC | 1 / 8 | 12.5000% |
| LULU | 2 / 7 | 28.5714% |
| PINS | 1 / 8 | 12.5000% |

The other70 companies have zero observed below outcomes (their scored denominators are in the full company table); these are small samples, not evidence that misses are impossible.

- LULU, 2025-05-05–2025-08-03: actual `1313a552-c473-5cc8-ac53-dcc71235eb81`, guidance `761d0e8e-cb2e-578f-b009-66c1bbd92387`. Exact source evidence remains in the pinned source record/JSON.
- LULU, 2026-05-04–2026-08-02: actual `2c226549-7d49-5601-952b-ec3eb4ac5efa`, guidance `35bdf649-0526-56e8-ad6b-6154e08e39d6`. Exact source evidence remains in the pinned source record/JSON.
- CNXC, 2026-06-01–2026-08-31: actual `805da867b75cd08720db2f77f8a4b99d0fdcf6acfb68242d601346154749b768`, guidance `d49167f9cd448c4bfd21620eb527efba369073b99b88d2c71e3a3934fbae9c06`. Exact source evidence remains in the pinned source record/JSON.
- PINS, 2026-07-01–2026-09-30: actual `c032c19e5c53eff10c6ccece883797d3bf040948a8fd65adc52cf71a99887c31`, guidance `796428e913bed65051bb7deb1b73ea58433ce41471ff78bb6ba736c15eed20b6`. Exact source evidence remains in the pinned source record/JSON.

| Descriptive industry group | Companies | Scored quarters | Below | Rate | Nominal 95% Wilson interval |
|---|---|---|---|---|---|
| Apparel and textile products (SIC 23) | 1 | 7 | 2 | 28.5714% | 8.2219%–64.1066% |
| Business services (SIC 73) | 36 | 262 | 2 | 0.7634% | 0.2096%–2.7401% |
| Electronic/electrical equipment (SIC 36) | 24 | 177 | 0 | 0.0000% | 0.0000%–2.1242% |
| Health services (SIC 80) | 2 | 14 | 0 | 0.0000% | 0.0000%–21.5311% |
| Industrial/computer machinery (SIC 35) | 4 | 28 | 0 | 0.0000% | 0.0000%–12.0643% |
| Instruments and related products (SIC 38) | 5 | 36 | 0 | 0.0000% | 0.0000%–9.6419% |
| Miscellaneous retail (SIC 59) | 1 | 8 | 0 | 0.0000% | 0.0000%–32.4408% |

Industry groups are the first two digits of contemporary SEC SIC metadata, **not GICS sectors or historical sector classifications**. SEC classifies lululemon as SIC2300 (apparel products), not retail, in the cached submissions. This explicit taxonomy avoids guessing sectors from names. Every company’s SIC, source URL, original retrieval timestamp and body hash are in `backtest_sectors.json`; sector metadata is descriptive only and never enters prediction selection. All 73 companies are covered.

Wilson formula: center=(p+z²/(2n))/(1+z²/n), half-width=z√[p(1−p)/n+z²/(4n²)]/(1+z²/n), z=1.959963984540054; endpoints clipped to [0,1]. Arithmetic uses Decimal. References: [NIST Wilson interval](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm), [SEC SIC classification](https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list).

## Paired company-cluster bootstrap — company-history subset

On 108 company-history predictions across 64 companies, the paired mean Brier difference (Smoothed minus walk-forward pooled) is -0.08345, with a 95% company-cluster bootstrap interval [-0.16700, 0.00402] (10,000 resamples, seed 20261121), which includes zero, but remains a selected retrospective comparison that does not capture cross-company dependence or establish live predictive quality.

Resample the 64 companies with replacement, drawing that many company clusters per resample and retaining every paired quarter in each selected cluster, including multiplicity. For each resample, divide the sum of Smoothed-minus-pooled quarter differences by the total number of resampled quarters; this targets the per-prediction mean, not an unweighted mean of company means. Compute the 2.5th/97.5th percentiles using linear interpolation at (10,000−1)×p. Company sizes are one or two quarters, so quarter counts vary across draws. Original predictions, training pools and probabilities are not refit. Exact case IDs/scores, fixed seed, cluster sizes and distribution/draw hashes are preserved in the companion JSON. No seed or interval tuning was performed.

The interval accounts for clustering within each company, conditional on this selected cohort and its fixed predictions. It does not account for dependence across companies from shared economic conditions or overlapping training sets, curation/survivorship, or choosing this subgroup after viewing results. It is not a fresh evaluation or a guarantee of performance on new issuers. The below-guidance Wilson interval above remains separate and is not made cluster-adjusted by this score comparison.

Reference for paired/percentile bootstrap terminology: [SciPy bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html). This implementation uses Python integer RNG draws and Decimal, not SciPy float arithmetic.
