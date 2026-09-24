# Session Handoff: Pier-Cap Ground-Structure STM

## Objective

Provide a practical production-oriented STM tool for pile-supported bridge pier
caps. The design STM is generated using a discrete ground structure so the
result is inherently truss-like.

## Work completed

- Added `stm_solver/ground_structure.py`.
- Added `tests/test_ground_structure.py`.
- Exported `optimize_pier_cap` from the package.
- Added a ground-structure usage section to `README.md`.
- Added the source-traceable FHWA benchmark catalog in
  `benchmarks/fhwa_nhi_130126.toml`.
- Added `stm_solver/benchmarks.py` and benchmark regression tests.
- Activated FHWA Example 2 as a prescribed-topology benchmark. Its reconstructed
  centerline geometry and published rounded forces use a documented 12% force
  tolerance; force sense and equilibrium are checked independently.
- Added `generate_frame_boundary_candidates` and `optimize_frame_boundary`.
  The frame-boundary forces are prescribed resultants from the adjoining region,
  not free support reactions. The generator recovers the FHWA Example 2 direct
  one-panel topology with the reconstructed compatible boundary resultants.
- Added `locate_linear_frame_boundary`, which integrates an FHWA-style linear
  compression stress diagram to place compression-resultant branches, and
  `optimize_frame_boundary_actions`, which constrains the branches by section
  axial force, shear, and moment. Boundary branches may be vertical, horizontal,
  or inclined; their vector contributions and moments are assembled in global
  coordinates. Explicit load-to-compression-block correspondence is supported
  through `connect_top_indices` metadata.
- The Example 2 tie force is no longer supplied. In accordance with the FHWA
  procedure, reinforcement fixes the tie location and equilibrium of the
  selected topology determines its force. Multi-compression-branch models are
  rejected as underdetermined unless load correspondence is explicit.
- Added this handoff file and `TODO.md`.
- Activated FHWA Example 3 as a prescribed global-STM benchmark. Its 16-node,
  29-member model reconstructs Figure 3-10, including distributed cap self-weight,
  hanger loads, moment-frame corner members, and the published column-interface
  forces. The reconstructed coordinates and displayed source values are rounded,
  so interface forces are admitted within a documented 3% band and the full force
  comparison uses a conservative 22% tolerance for this initial benchmark slice.
- Added optional signed member-force bounds to `optimize_ground_structure`; these
  allow rounded published interface forces to be imposed without falsely requiring
  exact numerical compatibility.
- Extended frame candidate generation for moment-frame corner fans, including
  multiple internal connections and links between boundary nodes. Example 3 now
  recovers all 29 published members from 33 candidates. The decisive modeling rule
  is that nonvertical cap webs are compression-only; otherwise the unconstrained LP
  substitutes diagonal tension shortcuts for several vertical hanger ties.
- Expanded `notebooks/stm_benchmarks.ipynb` with an Example 3 diagnostic figure.
  It overlays selected struts/ties and their signed forces on the rejected candidate
  set, and plots generated member forces against the published Figure 3-10 values.
- Made benchmark plotting non-blocking by selecting Matplotlib's inline backend,
  displaying figures explicitly, and closing them after display. This avoids an
  interactive `plt.show()` waiting indefinitely in some Jupyter front ends.
- Added `notebooks/pier_cap_design.ipynb` as the production-oriented railroad
  pier-cap scaffold. It uses user-defined component factors rather than invented
  AREMA defaults, validates inputs, solves named vertical-load combinations,
  compares topology, plots forces, and lists incomplete design gates. It also
  reports pile reactions and warns when the load-path objective leaves a support
  inactive; optimizer reactions are not a substitute for foundation analysis.
- Pier-cap diagonal top-to-bottom webs now default to compression-only, preventing
  the LP from replacing conventional hanger/chord reinforcement with arbitrary
  diagonal tension shortcuts. Added `find_member_crossings` and a notebook gate
  that stops on any remaining non-nodal selected-member intersection. The user's
  entered production-notebook inputs were preserved unchanged.
- Added first-pass design screens to `notebooks/pier_cap_design.ipynb` without
  changing the user's saved geometry, load, or combination inputs. The notebook
  envelopes member forces by geometric signature across combinations, calculates
  required tie steel and a preferred bar count, checks compression members using
  an explicitly assumed strut width, and screens load/pile bearing faces as
  external nodal zones. Factors, stress coefficients, assumed widths, and bar
  preferences are isolated in a separate preliminary-design input cell.
- Updated `stm_solver/design_checks.py` so tie, strut, and nodal factors are
  configurable. Nodal classification counts unique tension axes, preventing two
  collinear segments of one continuous tie from being misclassified as two ties.
- Established the typed pier-cap architecture in `stm_solver/pier_cap.py` and
  documented it in `docs/architecture.md`. `PierCapModel` validates canonical
  geometry, bearing loads, and pile/shaft supports while retaining compatibility
  with the existing ground-structure solver. `stm_solver/tables.py` exposes
  normalized records and optional pandas DataFrames; a database remains deferred.
- Moved load-component and combination assembly into tested package objects:
  `LoadPointForce`, `LoadComponent`, `LoadCombination`, and `PierCapLoadSet`.
  They enforce stable load-point IDs and coordinates, validate named factors and
  finite face widths, assemble factored bearing resultants, and check the cap
  envelope.
- Migrated `notebooks/pier_cap_design.ipynb` to the typed architecture. Its
  existing demonstration geometry, loads, factors, and preliminary design
  assumptions are preserved; finite face widths now live with the user inputs.
  The notebook constructs `PierCapLoadSet` and one `PierCapModel` per combination,
  solves through the model API, and exposes normalized pandas tables for each
  result. A fresh-kernel `nbconvert --execute` run passed with the prior load
  resultants, pile reactions, topology counts, crossing gate, and design tables.
- Added versioned JSON persistence for individual `PierCapModel` analysis cases
  and normalized CSV export for result tables. JSON round-trip tests re-solve the
  restored model and compare member forces. CSV export rejects unsafe table names.
  Added tested optional multi-sheet Excel export using pandas/openpyxl; sheet
  names are sanitized and de-duplicated. `openpyxl` is included in the notebook
  and tables optional dependencies.
- Extended `stm_solver/tables.py` with normalized records for nodal-zone
  geometries, finite-face tributaries, resolved member-force groups, and the
  preliminary strut, tie, and node checks. These adapters are tested separately
  from notebook presentation and can feed CSV, DataFrame, and future report output.
- Added the explicit multi-strut nodal-zone review workflow. An
  `ExternalNodalZonePlan` records engineer-selected member groups, face order,
  remote axis targets, back-face depth, and CCC/CCT/CTT classifications. The
  constructor rejects overlapping groups, resolves each group at the node,
  subdivides the finite face by normal force, revises each axis through its
  tributary centroid, and calculates its projected strut-interface width. The
  completed group output also flattens to one normalized audit table containing
  force components, tributary limits, revised axes, classifications, and widths.
- Finished the external nodal-zone implementation. External faces now carry an
  inward normal; each reviewed force tributary produces a bounded rectangular
  envelope polygon and a strut interface projected normal to its revised axis.
  `check_subdivided_nodal_zone_faces` screens the bearing, back, and projected
  strut-interface faces and reports normalized demand, area, capacity, D/C, and
  status records. Stress and confinement factors are deliberately explicit
  pending selection and verification of the governing code edition.
- Added `construct_single_strut_external_nodal_zone` as the safe production
  convenience path. It derives the plan only when exactly one compression strut
  enters an external face; multiple-strut nodes stop and require the explicit
  engineer-reviewed grouping/order/remote-target plan. The production notebook
  now constructs and checks all load and pile external zones for every solved
  combination, and exposes their geometry and three-face checks as DataFrames.
- Began geometry-derived strut-width calculation using the supplied 2025 AREMA
  Article 2.42 pages. `calculate_strut_width_profiles` maps constructed
  strut-to-node interfaces to compression-member ends, reports complete/partial/
  missing profiles, classifies equal-ended profiles as prismatic and unequal-ended
  profiles as tapered, and preserves the minimum end width as the controlling
  prismatic screen width. `strut_width_at` linearly interpolates only complete
  two-ended profiles. The production notebook exposes normalized width tables and
  runs geometry-derived capacity checks only for complete profiles; it never fills
  an unresolved end with the former assumed width.
  The engineering basis and limitation are recorded in `docs/strut_widths.md`.
- Added preliminary interior CCC/CCT interface construction for the production
  cap. The notebook explicitly declares continuous horizontal reinforcement,
  assigns effective tie faces between adjacent-node midpoints and cap ends,
  centers the permitted back-face depth on the tie centroid, separates transverse
  struts entering from opposite sides, and assigns tie-parallel compression to
  the rectangular node side face. Both demonstration combinations now have
  complete two-ended profiles for every compression member and use their minimum
  end width in the geometry-derived strut capacity screen.
- Added auditable strut-shape classification based on FHWA-NHI-130126 terminology.
  Equal complete profiles are prismatic; bottle-shaped classification requires a
  supplied midspan width greater than both ends; fan-shaped classification
  requires an explicit distributed-fan designation. Unequal ends without that
  evidence remain `tapered` with `field_evidence_required=True`. The notebook
  exposes normalized classification tables and empty reviewed-evidence maps;
  see `docs/strut_shapes.md`.
- Adopted the user's simplified conservative design policy. Compression capacity
  uses the minimum calculated end width; every non-prismatic member receives
  bottle-shaped detailing; no fan spreading is credited. The former 12-inch
  assumed-width production check was removed. Added a tested AREMA Article
  2.42.3.e orthogonal-grid selector enforcing the 0.003 ratios and the smaller of
  `d/4` and 12 inches. For the demonstration cap it selects two-leg No. 5 bars at
  4.5 inches vertically and horizontally, providing 0.0033 in each direction.
- Added automatic minimum longitudinal tie layouts. The selector searches standard
  No. 5 through No. 11 bars and checks required area, two-inch cover, the No. 5
  enclosure, 1.5-inch clear spacing, a conservative 12-inch transverse
  distribution limit, tie-zone depth, and a maximum of two layers. The notebook
  envelopes segment demands into common schedules: 4-No. 6 in one top layer
  (`As = 1.76 in^2`) and 5-No. 5 in one bottom layer (`As = 1.55 in^2`). All
  assumptions and remaining drawing checks are in `docs/reinforcement_layout.md`.
- Began tie development and anchorage without inventing missing code equations.
  `calculate_tie_end_anchorage_geometry` locates preliminary nodal-tributary
  critical sections, places bar ends inside cover and the enclosure, reports
  available straight lengths, and can compare reviewed straight/hooked/mechanical
  requirements when supplied. Current available lengths are 18.25/27.25 inches
  at the top left/right ends and 43.81/52.81 inches at the bottom left/right ends.
  These initially remained `REVIEW` because the original STM excerpt omitted
  Articles 2.14-2.21. The later supplied development excerpt now supports the
  straight-bar checks described in the following bullet. See
  `docs/development_anchorage.md`.
- Added AREMA 2025 Section 2.14 straight deformed-bar tension development after
  the user supplied Sections 2.14-2.21. The tested calculation reports the basic
  Eq. 2-8.1 length and each modification factor, enforces the 12-inch minimum,
  caps the combined top/epoxy factor at 1.7, and leaves the excess-steel reduction
  off by default. The production notebook now compares these requirements with
  the available tie-end lengths. Hooked/headed alternatives still need geometric
  fit checks; complete standard-hook detailing also needs AREMA Section 2.4.1.
  Current straight-bar requirements are 27.05 inches for the top 4-#6 layer and
  16.10 inches for the bottom 5-#5 layer. Straight anchorage is insufficient at
  the top-left end and adequate at the other three ends; the following bullet
  records the adopted standard-hook resolution.
- Added AREMA 2.17/2.4 standard-hook development and geometry plus AREMA 2.22.3
  Class A/B tension lap calculations. The notebook now resolves the former
  top-left failure with a standard 90-degree #6 hook: 10.18 inches required,
  4.5-inch inside bend, 9-inch tail, and 12-inch transverse projection, all
  fitting the current cap. The other three ends remain straight. Per Article
  2.22.3e and the user's direction to exclude headed/mechanical anchorages, STM
  longitudinal ties are continuous and unspliced; lap calculations remain
  available only for non-tie reinforcement.
- Extended FHWA Design Example 1 from force-flow benchmarking into published
  design-detail benchmarking. `run_fhwa_design_benchmark` now reproduces required
  bottom/vertical tie steel, the capacity of the published 16-#10 bottom tie,
  CCT and final CCC projected strut-interface widths, #10 hooked development,
  and the 25.4-inch available length to the extended prismatic-strut boundary.
  This also documents that the production cap's midpoint tributary anchorage
  boundary was only a preliminary proxy.
- Closed detailing items 4 and 5. The production notebook now extends both
  edges of every external prismatic strut to the applicable horizontal tie and
  envelopes the inward critical-section coordinate across load combinations.
  That check exposed a real deficiency in the former 4-No. 6 top schedule, so
  the compact-zone automatic schedule is now limited to No. 5 bars: 6-No. 5
  top with standard 90-degree hooks at both ends and 5-No. 5 bottom with straight
  development. Available/required lengths are 9.56/8.49 and 18.56/8.49 inches
  at the top, and 42.06/16.10 and 51.06/16.10 inches at the bottom; all pass.
  `design_tie_bar_layout` now enforces AREMA 2.5 clear spacing as the greatest
  of the baseline, 1.5 bar diameters, and twice the explicit maximum aggregate
  size. A normalized section-level cage gate checks longitudinal spacing,
  crack-grid spacing, layer spacing, hook fit, and anchorage. Both current cages
  pass for 0.75-inch aggregate. Full-length uncurtailed ties avoid lap/curtailment
  conflicts. Final 3D positioning is outside the analysis scope rather than an
  unresolved calculation gate.
  boundary remains a preliminary proxy; see `docs/design_benchmarks.md`.
- Completed the FHWA Example 1 capacity benchmark. A shared isolated nodal-face
  checker now reproduces CCT bearing and strut-interface capacities, all three
  initial CCC face checks, the two published failures, and the final 1,239-kip
  inclined-strut resistance after increasing the bearing to 14 inches. The
  benchmark compares areas, efficiency factors, capacities, D/C ratios, and
  status transitions. It also reproduces the 4.67-in2 required and 4.74-in2
  provided reinforcement for the deficient horizontal top strut.
- Completed canonical typed-input validation for unique IDs and physical
  locations, cap-envelope bounds, stable load-point coordinates across
  components, positive finite faces, and face endpoints within the cap length.
  New work should enter through these validated objects.
- Updated the README's primary pier-cap example to use the typed API and table
  adapters. Re-ran the migrated production
  notebook in a fresh kernel after the stricter validation; it still passes.

The optimizer uses separate nonnegative tension and compression variables and
solves nodal equilibrium with `scipy.optimize.linprog(method="highs")`. Its
objective is weighted force times member length. Positive returned force means
tension; negative returned force means compression.

## Important modeling decisions

1. The generation stage finds force flow, and the connected capacity calculations
   are preliminary screens only. They do not claim AREMA or AASHTO compliance.
2. Candidate nodes correspond to bearing, pile, and reinforcement-centerline
   locations rather than an arbitrary dense pixel grid.
3. Adjacent chord segments and angle-limited web members form the candidates.
4. Pile reactions are implicit at constrained DOFs and recovered after solving.
5. Member type is determined from the optimized force sign, avoiding conflicts
   between a guessed type and the solved behavior.
6. Frame boundaries and STMs are distinct: a boundary describes force exchange
   with the adjoining region, while the STM describes internal D-region load paths.
7. Arbitrary polygonal cross-section analysis is a separate side project, not a
   required input layer for the pier-cap tool. Local ledge/hanger STMs may reuse
   this project's generation and equilibrium machinery through explicit interface
   resultants, while retaining a separate geometry and input schema.
8. New pier-cap features should use the typed objects in `stm_solver.pier_cap`.
   Numerical work remains in tested package modules, normalized records or
   optional DataFrames support notebook review/export, and notebooks remain thin
   interactive clients. Do not add a database until persistent multi-project,
   revision-history, query, audit, concurrency, or integration needs justify it.
   See `docs/architecture.md`.

## Verification status

At the last completed check:

- `pytest -q`: 181 passed.
- `ruff check stm_solver tests`: passed.
- `notebooks/stm_benchmarks.ipynb` executes successfully through Jupyter with
  all three active FHWA force-flow cases passing. Its FHWA Example 1 design
  section also passes the published reinforcement, geometry, anchorage,
  nodal-face, final strut-resistance, reinforced-strut, D/C, and status-transition
  comparisons.
- `notebooks/pier_cap_design.ipynb` executes successfully through `nbconvert` in
  a fresh kernel using the typed model and normalized tables, including the
  preliminary tie and strut tables plus bounded external nodal-zone geometry
  and bearing/back/strut-interface check tables for every combination. It also
  reports calculated strut end-width profiles and withholds geometry-derived
  capacity checks until both nodal interfaces are available.
  In the current demonstration, all 17 compression members in each combination
  have complete profiles; the maximum preliminary geometry-width D/C is 0.101
  for `DEMO_VERTICAL` and 0.037 for `DEMO_DEAD_ONLY`.
  The classification table reports 2 prismatic and 15 tapered members for
  `DEMO_VERTICAL`, and 17 tapered members for `DEMO_DEAD_ONLY`; none are labelled
  bottle- or fan-shaped without reviewed field evidence.
  The adopted conservative policy is also executed: minimum end widths govern,
  non-prismatic members receive bottle detailing, fan credit is zero, and the
  orthogonal two-leg No. 5 at 4.5-inch grid passes in both directions. The final
  extended-strut anchorage check and section-level cage gate both pass for the
  schedules and lengths documented above.

The only pytest warning concerned sandbox permission to update `.pytest_cache`;
it was not a test failure. Jupyter is now installed and notebook verification
uses a true fresh-kernel `nbconvert --execute` run.

## How to continue

The product scope was clarified with the user. Keep normal notebook inputs
short, but leave consequential assumptions such as clear cover, aggregate size,
coating, concrete weight, preferred bar sizes, and code profile visible with
editable defaults. Derived geometry and reinforcement should remain automatic.
`TODO.md` is now organized into core completion work, conservative automated
defaults, optional/research enhancements, work explicitly outside the tool, and
a separately scoped polygonal/local-STM project. Three-dimensional bar placement
and shop drawings are downstream detailing responsibilities, not analysis gates.

The core requirements were then implemented. `optimize_pier_cap_load_cases`
generates one candidate structure from common physical load/support locations,
solves every case, removes candidates unused by every case, and re-solves until
the common set is stable. It preserves candidate provenance/rejection reasons,
aligned force tables, and explicit force-reversal records. The demonstration
starts with 64 candidates, retains 31 after one pruning iteration, and reports
two bottom-chord reversals between `DEMO_VERTICAL` and `DEMO_DEAD_ONLY`; the
common reinforcement/strut envelopes design both signs.

Interior node-face capacity is now connected to the production notebook using
the conservative continuous-tie/midpoint geometry, separated opposite sides,
no confinement enhancement, and no fan credit. Each demonstration combination
constructs 25 interfaces and checks 75 faces; maximum D/C is 0.184 and 0.074.
AREMA 2025 Table 8-2-9 is implemented by face, including `k1 = 0.85-f'c/20`
and the 0.45-to-0.65 interface bounds. This corrected the former generic CCT
and interface factors.

Added a hand-solvable symmetric two-panel benchmark, model-quality metrics,
complete normalized calculation records, optional CSV/JSON/Excel export, and a
concise Markdown calculation summary. The notebook keeps cover, aggregate,
weight/coating, preferred bars, hook permission, output options, and the code
profile visible with defaults. Fresh-kernel execution passes.

The user subsequently supplied AREMA 2025 Article 2.30.2b. It verifies
`phi = 0.70` for STM compression and `phi = 0.90` for reinforced-concrete STM
tension; it also states that development and splice provisions do not require
an additional resistance factor. Added a tested named-factor resolver, changed
the production compression/nodal factor from the former provisional 0.75 to
0.70, and removed the provisional code-profile warning.

From the repository root:

```powershell
pytest -q
ruff check stm_solver tests
jupyter notebook notebooks/pier_cap_ground_structure.ipynb
```

All core requirements currently identified in `TODO.md` are complete. Remaining
unchecked work is optional enhancement, research, or explicitly outside the
two-dimensional tool scope.

## HTML calculation report (2026-09-22)

Added a self-contained, print-ready HTML report in `stm_solver.reporting` and
connected it to the production pier-cap notebook. A normal notebook execution
now writes `output/pier_cap/pier_cap_report.html` alongside the existing
Markdown, JSON, and CSV outputs. The first report design includes an executive
status row, visible inputs and code basis, one inline SVG force-flow figure per
combination, reinforcement and anchorage summaries, ranked D/C bars, model
quality and force-reversal tables, a calculation-table index, and an explicit
scope/limitations statement. The HTML has no external assets or JavaScript and
includes responsive and print CSS.

Fresh-kernel notebook execution completed and generated a 20.9 kB report with
seven report sections and two force-flow SVGs for the demonstration cases. The
HTML parser audit passed, the two focused reporting tests pass, Ruff passes, and
the accessible test set passes 192 tests total (182 plus 10 in the pier-cap
module, with four temporary-directory tests deselected because this sandbox
cannot access pytest's temporary directory). The in-app browser was unavailable
in this session, so rendered desktop/print visual QA remains the immediate next
review step when that preview surface is attached.

The user then supplied a four-page browser-generated PDF. Visual review found
the engineering content clear and the force-flow figures legible, but exposed
print-only layout defects: a split design-basis callout, merged cover metadata,
an orphan fifth summary card, suppressed D/C bar fills, and stranded section
headings. The HTML print CSS now preserves colors, forces five compact summary
cards across, prevents callout splitting, separates metadata fields, adds
reinforcement/anchorage subheads, begins Model Review on a new page, and opens
the audit-table index for printed output. The notebook was rerun successfully;
request a new PDF export for final visual confirmation of these corrections.

The user requested stronger traceability and more technical data. Force-flow
SVGs now label every active member with its diagram member ID and signed force
in kip, and label all nodes with `N#` references. Governing utilization rows now
identify the actual `M#` member or the `N#`, nodal group, and face type instead
of displaying an unexplained sequence number. A new collapsible technical-data
section contains the complete node-coordinate reference plus, for every load
combination, member forces, reactions, strut checks, external nodal faces, and
interior nodal faces. Normalized force records now carry both the load-case
local member ID used by diagrams/checks and the persistent candidate ID used
for provenance. The notebook was rerun and regenerated the HTML/JSON/CSV files.

A second 10-page PDF was visually reviewed. The five-card summary and D/C bars
now print correctly, and the technical tables are readable, but open `<details>`
blocks and a forced Model Review page break created large blank page areas.
Removed those print constraints so open tables paginate naturally and Model
Review follows the utilization section. Added `Expand all` and `Collapse all`
buttons scoped to the technical tables, using embedded dependency-free
JavaScript; buttons are hidden when printing. The plot now omits labels for
unused/isolated nodes, and cover metadata has explicit separators. Regenerated
the report and reran the focused reporting tests and Ruff successfully.

## Versioned FHWA production-validation package (2026-09-23)

Created `validation/fhwa_example_1/v1.0.0/`. The folder uses a semantic package
version because its identity covers the source interpretation, mapping,
comparison quantities, and tolerances; Git commit provenance belongs in the
manifest and generated reports rather than in a folder name. Downloaded the
official 196-page FHWA-NHI-13-0126 solved-example PDF from GovInfo into the
package. The 3,048,582-byte file has SHA-256
`BE2F93DD890FC1CDD4128109A32ACECDD1878313E1FAE05F8E27F9AF447C7A8D`.

The package also includes a provenance manifest, frozen Example 1 input and
published values, an integrity command, a mapping from FHWA concepts to
production inputs, required comparison fields and interpretation limits, and
the implementation sequence for a true production-path benchmark. The source
commit observed when the package was created was `1bc2f795e9d6` with a dirty
worktree. No Git commit was created; the repository contains numerous earlier
and unrelated modifications, so any checkpoint commit must be deliberately
staged rather than committing the whole worktree.

## Optional reinforcement verification (2026-09-23)

The production notebook now exposes one optional `provided_reinforcement`
block immediately below the visible detailing defaults. It remains `None` for
the normal automatic-design workflow. Users may independently override the top
tie, bottom tie, or both orthogonal crack-control directions. Longitudinal
inputs require only bar count, bar size, and optional layer count. Grid inputs
use total steel area crossing the section at each spacing interval and spacing
in inches; for example, two No. 5 legs are entered as 0.62 in2 at the chosen
spacing. Missing portions continue to be designed automatically.

Added tested package functions to check fixed longitudinal arrangements for
steel area, cover/aggregate spacing, layer fit, and maximum spacing, and to
check user-supplied vertical/horizontal grid area, reinforcement ratio, and
spacing limit. Provided reinforcement flows through development, hook,
anchorage, and cage checks. The HTML report now states required versus selected
or provided longitudinal steel and gives area per set, spacing, required and
provided ratios, and status for both crack-control directions. Eighty focused
design/reporting tests pass, Ruff passes, and the default automatic notebook
executes successfully in a fresh kernel.

## Artifact versioning (2026-09-23)

Added lightweight audit versioning in `stm_solver.versioning`. The package/tool
version remains aligned with `pyproject.toml` at 0.1.0; the pier-cap notebook
template and HTML report format begin at 1.0.0. The notebook carries its template
identity/version in notebook metadata and exposes an editable project revision
in the normal project input block. Every execution records the UTC generation
time, Git source commit and dirty-worktree state when available, plus stable
16-character SHA-256 fingerprints for the complete calculation inputs and
normalized results. Result fingerprints are computed before metadata is added,
so timestamps do not make deterministic calculations appear different.

The metadata is written into JSON/CSV output as `report_metadata`, printed in
the Markdown summary, and displayed in a compact Document Control grid near the
front of the HTML report. The version/fingerprint unit test, reporting tests,
Ruff, and fresh-kernel notebook execution pass. Current demonstration revision
is 0; its IDs are regenerated whenever an input or calculated result changes.

## Adopted support-reaction workflow (2026-09-24)

The TxDOT 5-5253-01-1 Chapter 4 validation demonstrated that the existing STM
ground-structure objective can satisfy equilibrium while selecting a materially
different reaction distribution for an indeterminate five-support cap. TxDOT's
worked example instead obtains column reactions from a continuous-beam analysis
and imposes both the applied loads and those reactions on the global STM. The
current TxDOT Bridge Design Manual also permits trestle-pile and multi-column
caps to be analyzed as continuous beams on knife-edge supports at pile/column
centerlines in lieu of a more detailed analysis.

The adopted normal workflow is therefore:

1. Analyze the cap as a continuous beam at the pile/column centerlines, using
   one pin and the remaining supports as vertical rollers.
2. Calculate a reaction set for each supplied load combination.
3. Apply the original loads and calculated reactions as fixed boundary forces
   to the STM.
4. Optimize/solve only the internal STM load path; do not allow the STM
   objective to redistribute reactions.
5. Verify force and moment equilibrium and report the reaction model and its
   assumptions.

The pin/roller model is a simplified vertical-load analysis that neglects
support settlement and finite pile/column/soil-spring flexibility. Retain a
prescribed-reaction override for reactions obtained from a reviewed frame,
foundation, or soil-structure model. Flag possible refinement when supports
have materially different stiffnesses or lengths, columns are unusually wide,
soil conditions vary, scour or differential settlement matters, uplift is
possible, connection fixity is important, or lateral/seismic actions govern.

This entry records an approved implementation direction, not completed code.
Do not mark the related TODO items complete until the beam solver, STM boundary
transfer, reporting, and TxDOT reaction benchmark are implemented and tested.
