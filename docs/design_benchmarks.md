# Design-calculation benchmarks

## Purpose

The FHWA-NHI-130126 examples are used as independent numerical benchmarks for
calculations common to the FHWA/AASHTO and AREMA workflows. Passing means an
isolated calculation reproduces a published intermediate value. It does not mean
the standards are interchangeable or that a full design complies with both.

The frozen source, checksum, Example 1 reference values, and production-path
comparison plan are retained in
`validation/fhwa_example_1/v1.0.0/`. The semantic folder version identifies the
validation package; generated reports separately record the repository commit.

## FHWA Design Example 1

The source-traceable values are stored in `benchmarks/fhwa_nhi_130126.toml`.
`run_fhwa_design_benchmark` currently checks:

| Calculation | Published | Calculated |
|---|---:|---:|
| Bottom tie required area | 18.76 in2 | 18.76 in2 |
| 16-#10 bottom tie factored capacity | 1,097 kip | 1,097 kip |
| Vertical tie required area | 11.11 in2 | 11.11 in2 |
| CCT strut interface, 12-in bearing and 10-in back face | 14.7 in | 14.7 in |
| Final CCC strut interface, 14-in bearing and 6-in back face | 12.3 in | 12.3 in |
| #10 hooked-bar basic development | 21.6 in | 21.6 in |
| #10 hooked-bar required development with excess steel | 19.9 in | 19.9 in |
| Available length to extended prismatic-strut boundary | 25.4 in | 25.4 in |
| CCT bearing-face capacity | 1,411 kip | 1,411.2 kip |
| CCT bearing-face D/C | 0.425 | 0.425 |
| CCT strut-interface capacity | 1,482 kip | 1,482.6 kip |
| CCT strut-interface D/C | 0.794 | 0.794 |
| Initial CCC bearing-face capacity | 1,713 kip | 1,713.6 kip |
| Initial CCC bearing-face D/C | 0.350 | 0.350 |
| Initial CCC back-face capacity | 856 kip | 856.8 kip |
| Initial CCC back-face D/C | 1.183 (NG) | 1.182 (NG) |
| Initial CCC inclined-strut capacity | 1,138 kip | 1,138.2 kip |
| Initial CCC inclined-strut D/C | 1.034 (NG) | 1.034 (NG) |
| Final CCC inclined-strut capacity | 1,239 kip | 1,239.0 kip |
| Final CCC inclined-strut D/C | 0.950 (OK) | 0.950 (OK) |
| Required top-strut reinforcement | 4.67 in2 | 4.67 in2 |
| Provided top-strut reinforcement | 4.74 in2 | 4.74 in2 |

The reinforcement selection is not forced to match the example. FHWA begins
with a previously assumed 16-#10 layout, while this project's selector searches
for minimum area subject to its detailing rules. The benchmark compares required
area and the capacity of the published layout separately.

The anchorage benchmark exposed a useful production-model refinement. FHWA
locates the critical section where the tie exits the extended edge of a prismatic
strut. The pier-cap notebook now constructs that boundary from each actual
external nodal geometry and envelopes it across load combinations.

## Capacity iteration and rounding

The benchmark preserves the example's initial failed CCC back and inclined-strut
faces, then verifies the final 1,239-kip inclined-strut resistance after the
bearing grows from 12 to 14 inches. It also reproduces the 4.67-in2 steel area
required to supplement the deficient horizontal top-strut face and the provided
6-#8 area of 4.74 in2.

FHWA displays capacities to whole kips. D/C values are therefore source-derived
from the displayed demand and capacity rather than printed directly in the
manual. The comparison tolerances allow only the rounding propagated by those
whole-kip values. Crack-control layouts remain qualitative comparisons because
FHWA's practical spacing choices need not equal the selector's largest
permissible spacing even when both satisfy the 0.003 ratio.

## Hand-solvable multi-panel check

A source-independent symmetric two-panel truss supplements the published
examples. With equal load `P` at its two top nodes, it verifies `P` tension in
both bottom panels, `P` compression in the top chord, `sqrt(2)P` compression in
the two outer 45-degree diagonals, zero force in the two center diagonals, and
`P` vertical reaction at each end. This gives the equilibrium solver a
transparent regression that does not depend on interpreting a published figure.
