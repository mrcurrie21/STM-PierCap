# Production-path comparison plan

## Objective

Demonstrate that the production pier-cap workflow reproduces the independently
solved FHWA Example 1 quantities within source-appropriate tolerances. The run
must use the same analysis function, normalized records, version metadata, and
HTML report generator as a project calculation.

## Mapping to the production model

| FHWA item | Production representation |
|---|---|
| Two 600-kip loads | Finite top bearing resultants at x = 120 and 204 in |
| End reactions | Finite support faces centered at x = 12 and 312 in |
| Deep-beam envelope | 324-in by 72-in two-dimensional cap region |
| STM chord centerlines | Bottom y = 5 in and top y = 69 in; 64-in separation |
| Final bearing faces | 14-in length by 48-in beam width |
| Published truss | Automatically generated production ground structure |
| Published bar layout | Optional provided-reinforcement verification input |
| Published nodal dimensions | Benchmark comparison targets, not hidden inputs |

Finite face widths not explicitly used in the force-only source model must be
documented when the full production case is encoded. They may not be tuned
silently merely to force agreement.

## Required comparisons

1. Total applied load and recovered reactions.
2. Equilibrium residual.
3. Primary diagonal and chord forces.
4. Required bottom and vertical tie steel.
5. Capacity of the published 16-#10 bottom-tie arrangement.
6. CCT and CCC interface geometry.
7. Bearing, back-face, and strut-interface capacities and D/C ratios.
8. Initial documented CCC failures and final documented passing geometry.
9. Hook development and available anchorage length.
10. Required and provided reinforced-strut steel.
11. Crack-control grid comparison, identified as qualitative where the
    production selector chooses another compliant spacing.

## Comparison output

The validation appendix shall include:

| Field | Meaning |
|---|---|
| Quantity | Human-readable calculation name |
| Source page | Location in the archived PDF |
| Published | Frozen reference value |
| Computed | Production-pipeline value |
| Computed/published | 1.000 is an exact match |
| Difference | Signed and percentage difference |
| Tolerance | Documented acceptance threshold |
| Status | PASS, FAIL, or QUALITATIVE |

## Interpretation limits

- Agreement validates the exercised production path; it does not establish
  general compliance with every FHWA, AASHTO, or AREMA provision.
- A different automatically selected reinforcement layout is acceptable when
  required area and the capacity of the published layout both compare correctly.
- Additional secondary ground-structure members do not constitute failure when
  equilibrium and published primary load-path invariants pass.
- Every deviation must be visible; no undocumented calibration is permitted.

## Implementation sequence

1. Extract notebook orchestration into `run_pier_cap_design(...)`.
2. Make the production notebook call that function for its demonstration case.
3. Add an adapter that creates the FHWA production input from this package.
4. Generate the standard versioned report plus validation appendix.
5. Add an automated regression test and retain the generated comparison output.
