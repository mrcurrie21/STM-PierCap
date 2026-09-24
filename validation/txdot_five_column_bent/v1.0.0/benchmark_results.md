# TxDOT Five-Column Bent Global STM Validation

## Outcome

The published Figure 4.10 global STM and the eligible published tie/bearing calculations are internally consistent. The production notebook does **not** reproduce the published five-column reactions, so its automatically selected topology and member forces cannot be accepted as a like-for-like validation of Figure 4.10.

No production code was changed.

## Production reaction comparison

| Support | TxDOT (kip) | Notebook (kip) | Difference | Status |
|---|---|---|---|---|
| C1 | 440.2 | 399.7 | -9.2% | FAIL |
| C2 | 620.0 | 748.1 | +20.7% | FAIL |
| C3 | 680.5 | 354.8 | -47.9% | FAIL |
| C4 | 918.5 | 1346.6 | +46.6% | FAIL |
| C5 | 499.7 | 309.9 | -38.0% | FAIL |

Notebook equilibrium residual: 2.27e-13 kip (PASS). The issue is reaction selection, not equilibrium.

## Published global-joint statics

| Non-support node | Residual (kip) | Status |
|---|---|---|
| A | 0.113 | PASS |
| L | 0.331 | PASS |
| P | 0.871 | PASS |

## Published tie calculations

| Check | Calculated | Published | Difference | Status |
|---|---|---|---|---|
| Top longitudinal tie P-Q | 10.191 | 10.190 | +0.01% | PASS |
| Bottom longitudinal tie FF-GG | 5.569 | 5.570 | -0.03% | PASS |
| Vertical tie L-FF | 4.407 | 4.410 | -0.06% | PASS |
| Vertical tie L-FF, 2-leg #5 | 8.046 | 8.000 | +0.58% | PASS |
| Vertical tie P-II | 4.028 | 4.030 | -0.06% | PASS |
| Vertical tie P-II, 4-leg #5 | 7.112 | 7.100 | +0.16% | PASS |

## Eligible non-column node check

Critical girder bearing at Node P: 305.76 kip calculated versus 306 kip published (PASS).

## Exclusions

- Column-support nodes EE, JJ, and NN are excluded.
- Published node/strut-interface checks at P, Q, R, and V are also excluded because their final geometry uses strut angles revised after column-node subdivision.
- Consequently, Chapter 4 contains no remaining standalone non-column strut-capacity check on the unmodified global geometry.

## Validation finding

A future prescribed-reaction input is needed for a true end-to-end Figure 4.10 comparison. The reactions must come from the adjoining frame/continuous-beam analysis; they should not be selected by the STM topology objective for this indeterminate five-support cap.
