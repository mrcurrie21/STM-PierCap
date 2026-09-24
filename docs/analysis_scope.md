# Pier-cap STM analysis scope

The production workflow is a two-dimensional strut-and-tie analysis for
pile-supported bridge pier caps. It intentionally separates calculations that
can be automated reliably from project design and detailing decisions.

## Calculated by the tool

- vertical support reactions from a continuous cap-beam analysis using one pin
  and the remaining supports as vertical rollers, followed by application of
  those reactions as fixed boundary forces in the STM (adopted direction;
  implementation pending);
- one common, pruned candidate structure for every supplied load combination;
- STM equilibrium, selected members, provenance, and force reversals;
- force envelopes and a common longitudinal reinforcement schedule;
- finite bearing and pile/shaft faces and external nodal-zone geometry;
- conservative interior nodal zones using continuous ties, midpoint
  tributaries, separated opposite sides, and no confinement enhancement;
- strut widths and conservative capacities;
- tie steel, crack-control steel, development, standard hooks, aggregate-based
  spacing, and section-level compatibility;
- normalized CSV/JSON/Excel-ready tables, model-quality metrics, and a concise
  Markdown calculation summary.

## Visible defaults

Clear cover, maximum aggregate size, concrete weight, coating, preferred bar
sizes, standard-hook permission, ground-structure angles, and the code profile
remain visible and editable in the notebook. The results repeat the defaults
that were actually applied. Bar counts, development lengths, hook selection,
nodal back depths, and other derived quantities are automatic.

## Reaction-analysis policy

For the normal vertical-load workflow, the cap is treated as a continuous beam
over knife-edge supports at the pile or column centerlines. One support is a pin
and the remaining supports are rollers; all supports restrain vertical
translation, while only the pin supplies nominal horizontal stability. The beam
analysis determines reactions for each load combination. The STM then treats
the applied loads and those reactions as prescribed boundary forces and solves
only the internal load path.

This simplified reaction model assumes negligible support settlement and does
not represent pile/column or soil-spring flexibility. A prescribed-reaction
input remains necessary when reactions come from a reviewed frame, foundation,
or soil-structure model. Refinement should be considered for unusually wide
columns, materially different pile/column stiffnesses or lengths, variable soil
conditions, scour, differential settlement, uplift, significant connection
fixity, or governing lateral/seismic actions.

The STM topology objective must not select the reaction distribution of an
indeterminate multi-support cap.

## Outside the tool

The user supplies applicable project loads or factored load cases. Refined
global frame analysis, support-settlement analysis, soil-structure interaction,
bearing/foundation design, final three-dimensional bar positioning, clash
review, drawings, fabrication, and design approval remain outside this
two-dimensional analysis. These are scope boundaries, not failed notebook
checks.

## Code-profile status

The supplied references support the implemented AASHTO strut equation and the
AREMA 2025 tie, nodal-face, crack-control, development, hook, and splice
calculations. AREMA Table 8-2-9 is implemented by face: CCC bearing/back 0.85,
CCT bearing/back 0.70, CTT bearing/back `k1`, and strut-to-node interfaces use
`k1` bounded from 0.45 to 0.65, where `k1 = 0.85 - f'c/20` for ksi units.

AREMA 2025 Article 2.30.2b specifies `phi = 0.70` for compression in
strut-and-tie models and `phi = 0.90` for reinforced-concrete tension in
strut-and-tie models. These factors are implemented in the named code profile.
The same excerpt confirms that reinforcement development and splice provisions
do not require an additional resistance factor.
