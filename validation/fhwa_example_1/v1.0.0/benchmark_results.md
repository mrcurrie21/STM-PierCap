# FHWA Design Example 1 benchmark results

Overall status: **PASS**

This report covers the active source-backed direct-strut force/topology benchmark. FHWA Table 1-3 explicitly accepts this symmetric direct-strut alternative to the instructional two-panel left side.

- Source pages: 27, 36, 37
- Candidate members: 16
- Equilibrium residual: 0 kip
- Case force tolerance: +/-1 kip

| Quantity | Published | Computed | Computed / published | Difference | Tolerance | Status |
|---|---:|---:|---:|---:|---:|---|
| Left vertical reaction (kip) | 600.0000 | 600.0000 | 1.0000 | 0.0000 | +/-1.0000 | PASS |
| Right vertical reaction (kip) | 600.0000 | 600.0000 | 1.0000 | 0.0000 | +/-1.0000 | PASS |
| Primary diagonal compression (kip) | 1176.9266 | 1176.9266 | 1.0000 | -0.0000 | +/-1.0000 | PASS |
| Primary chord force (kip) | 1012.5000 | 1012.5000 | 1.0000 | 0.0000 | +/-1.0000 | PASS |
| Equilibrium residual (kip) | 0.0000 | 0.0000 | - | 0.0000 | +/-0.0000 | PASS |

Individual checks:

- equilibrium: PASS
- vertical_reactions: PASS
- diagonal_compression: PASS
- chord_forces: PASS
