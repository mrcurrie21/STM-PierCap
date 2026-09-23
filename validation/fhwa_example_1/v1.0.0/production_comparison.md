# FHWA Example 1 production-notebook comparison

Overall status: **PASS WITH DOCUMENTED GAP**

The production notebook code cells are unchanged except for the designated input cell. The automatically selected symmetric direct-strut topology is explicitly accepted by FHWA Table 1-3 as an alternative to the instructional two-panel left side.

| Quantity | Source | Published | Production | Difference | Tolerance | Status | Note |
|---|---|---|---|---|---|---|---|
| Left reaction (kip) | Fig. 1-8 | 600.0 | 600.0 | 0.0 | +/-1 | PASS |  |
| Right reaction (kip) | Fig. 1-8 | 600.0 | 600.0 | 0.0 | +/-1 | PASS |  |
| Direct diagonal compression (kip) | Table 1-1, CF | 1177.0 | 1176.926611985641 | -0.07338801435889764 | +/-1 | PASS |  |
| Direct chord force (kip) | Table 1-1, BC/EF | 1013.0 | 1012.5 | -0.5 | +/-1 | PASS |  |
| Bottom tie required area (in2) | Design Step 7 | 18.76 | 18.75 | -0.010000000000001563 | +/-0.02 | PASS |  |
| 16-No.10 provided area (in2) | Fig. 1-4 | 20.32 | 20.32 | 0.0 | +/-0.01 | PASS |  |
| 16-No.10 factored tie capacity (kip) | Design Step 7 | 1097.0 | 1097.28 | 0.2799999999999727 | +/-1 | PASS |  |
| Final CCC back-face capacity (kip) | Design Step 8 | 856.0 | 856.8 | 0.7999999999999545 | +/-1 | PASS |  |
| Final CCC back-face D/C | Design Step 8 | 1.1834 | 1.1817226890756303 | -0.0016773109243697348 | +/-0.005 | PASS |  |
| Final CCC strut-interface width (in) | Design Step 8 | 12.3 | 12.2989826660293 | -0.0010173339707009177 | +/-0.05 | PASS |  |
| Final CCC strut capacity (kip) | Design Step 8 | 1239.0 | 1239.737452735753 | 0.7374527357530951 | +/-2 | PASS |  |
| Final CCC strut D/C | Design Step 8 | 0.95 | 0.9493353688625716 | -0.0006646311374283176 | +/-0.005 | PASS |  |
| Vertical crack-control area per spacing (in2) | Design Step 9 | 1.24 | 1.24 | 0.0 | +/-0.001 | PASS |  |
| Vertical crack-control spacing (in) | Design Step 9 | 8.0 | 8.0 | 0.0 | +/-0.001 | PASS |  |
| Horizontal crack-control area per foot (in2) | Design Step 9 | 1.76 | 1.76 | 0.0 | +/-0.001 | PASS |  |
| Horizontal crack-control spacing (in) | Design Step 9 | 12.0 | 12.0 | 0.0 | +/-0.001 | PASS |  |
| Hook development required (in) | Design Step 10 | 19.9 | 17.242091752452776 | -2.6579082475472227 | QUALITATIVE | BASIS DIFFERENCE | Production notebook applies AREMA development provisions; FHWA applies AASHTO LRFD. |
| Hook anchorage available (in) | Fig. 1-21 | 25.4 | 24.177500000000002 | -1.2224999999999966 | QUALITATIVE | PASS | Different bar-end convention; both calculated lengths exceed their governing requirement. |
| Top compression-chord reinforcement | Design Step 8 | 6-No.8 (4.74 in2) | Concrete-only NG; 856.8 < 1012.5 kip | - | FUNCTIONAL | GAP | Production identifies the same deficiency but does not accept/design supplemental compression-strut steel. |

The validation identified and corrected two shared-analysis defects: provided crack-control grids lost their bar-size metadata before cage checks, and finite-face transfer links were incorrectly treated as design struts instead of connecting the physical face to the actual STM node.
