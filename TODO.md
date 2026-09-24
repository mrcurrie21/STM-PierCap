# Pier-Cap STM Development TODO

This file tracks the two-dimensional pile-supported bridge pier-cap STM tool.
The core product generates and checks a statically admissible STM from
user-supplied geometry, factored loads, and supports. It does not attempt to
replace project load development, foundation design, reinforcing drawings, or
three-dimensional constructability review.

## Input philosophy

Keep the normal notebook input area short, visible, and easy to edit. Inputs
such as clear cover should remain visible with reasonable default values rather
than being hidden inside the implementation.

### Basic project inputs

- Cap length, depth, and width.
- Concrete strength and reinforcement yield strength.
- Pile/shaft locations, restraint types, and finite face widths.
- Bearing/load locations, finite face widths, and applied forces.
- User-supplied load cases or factored load combinations.

### Visible inputs with defaults

- Clear cover.
- Maximum aggregate size.
- Normal-weight or lightweight concrete.
- Uncoated or epoxy-coated reinforcement.
- Preferred minimum and maximum longitudinal bar sizes.
- Continuous, uncurtailed STM tie policy.
- Standard-hook permission; headed/mechanical anchorage remains disabled by
  current project direction.
- Ground-structure angle limits.
- Code profile/edition after the implemented provisions are verified.

The notebook should calculate tie elevations, nodal back depths, crack-control
reinforcement, bar counts, development lengths, hook selection, and other
derived quantities. Advanced overrides may remain available, but should not be
required for a normal run. Every applied default must be reported in the
calculation results.

## Core work required for a complete analysis tool

These items are part of the intended product and should be completed before the
tool is presented as a code-based pier-cap STM analysis.

### Common model across load combinations

- [x] Scaffold a production-oriented notebook with user-defined load combinations.
- [x] Envelope selected-member forces across the solved vertical-load combinations.
- [x] Solve all combinations on one common candidate ground structure.
- [x] Identify force reversals and members that alternate between strut and tie.
- [x] Produce one common reinforcement layout based on the common-model force
      envelope, designing reversal members for both force signs.
- [x] Add controlled member pruning followed by equilibrium re-solution.
- [x] Add explicit candidate-member provenance and rejection reasons.

### Interior nodes and code checks

- [x] Define and document the conservative geometry and capacity policy for
      interior/smeared nodal zones.
- [x] Complete interior node-face capacity checks.
- [x] Complete code-profile verification for the implemented STM checks.
  - [x] Verify the AASHTO strut equation against the supplied 2014 excerpt and
        the FHWA published-example benchmarks.
  - [x] Verify AREMA 2025 tie, node-face, crack-control, development, hook, and
        splice equations against the supplied excerpts.
  - [x] Implement face-specific AREMA Table 8-2-9 nodal factors, including the
        concrete-strength-dependent strut-interface factor.
  - [x] Verify AREMA 2025 Article 2.30.2b resistance factors: 0.70 for STM
        compression and 0.90 for reinforced-concrete STM tension. Development
        and splice provisions do not receive an additional resistance factor.

### Essential validation and reporting

- [x] Add a hand-solvable multi-panel verification problem.
- [x] Add concise model-quality metrics: member count, obvious congestion,
      load-path length, and equilibrium residual.
- [x] Export selected nodes, members, forces, reactions, reinforcement, and
      design checks to the existing CSV/JSON result framework.
- [x] Generate a concise, portable HTML engineering calculation report with
      inputs, visible defaults, force-flow figures, reinforcement and anchorage,
      ranked governing checks, model-quality data, scope, and audit-table index.

## Conservative automated defaults

These checks belong in the tool, but should normally run without additional
user input. A user may opt into a refinement when less-conservative treatment
is justified.

### Ground structure and equilibrium

- [x] Preserve the existing continuum FEM/BESO workflow as optional guidance.
- [x] Add discrete pier-cap candidate-member generation.
- [x] Add equilibrium-constrained linear-programming optimization.
- [x] Classify selected members from solved force sign.
- [x] Report pile reactions and equilibrium residuals.
- [x] Add a runnable demonstration notebook.
- [x] Add typed-model validation for geometry bounds, duplicate load/support IDs
      and locations, stable component coordinates, and finite-face bounds.
- [x] Detect non-nodal crossing members and stop the production notebook for review.
- [x] Default pier-cap diagonal web candidates to compression-only.
- [x] Add frame-boundary candidate generation with prescribed interface resultants.
- [ ] Retain an advanced opt-in for diagonal tie candidates with an explicit
      detailing warning; do not expose it in the normal workflow.

### External and interior nodal geometry

- [x] Represent bearing plates and pile/shaft heads as finite external faces.
- [x] Construct and benchmark projected geometry for singular external nodes
      with one compression strut.
- [x] Subdivide finite faces into force tributaries for multi-strut nodes.
- [x] Benchmark uniform-pressure tributaries against FHWA Example 3 Node G.
- [x] Revise supplied strut axes through tributary-face centroids.
- [x] Resolve explicitly grouped adjacent member forces into design struts.
- [x] Add a typed engineering-review plan for member-resolution groups,
      tributary order, remote axis targets, and node classifications.
- [x] Construct bounded nodal-envelope polygons and projected strut interfaces.
- [x] Check bearing, back, and strut-interface faces with explicit factors.
- [x] Construct compatible interior interfaces using continuous reinforcement
      and midpoint tributaries as the conservative default.
- [ ] Support split/double nodes at column bearing regions. Permit a global STM
      column reaction to be expanded into a reviewed local STM with multiple
      column-face nodes, revised local strut angles, and equilibrium-preserving
      force transfer between the global and local models.

### Strut geometry and design

- [x] Determine strut width at both ends and along each strut.
- [x] Assemble external nodal-interface widths by compression-member ID.
- [x] Report complete, partial, and missing profiles without substituting an
      assumed width.
- [x] Interpolate complete two-ended profiles and use the minimum end width for
      the conservative prismatic capacity screen.
- [x] Distinguish prismatic, bottle-shaped, fan-shaped, and tapered envelopes
      without inferring bottle/fan behavior from unequal end widths alone.
- [x] Apply the simplified policy: minimum end width controls, non-prismatic
      members receive bottle-shaped detailing, and no fan credit is taken.
- [ ] Allow optional reviewed mid-field/topology evidence only when a project
      seeks less-conservative member-specific detailing.

### Reinforcement and anchorage

- [x] Calculate tie steel area and automatically select bar counts and layers.
- [x] Generate common enveloped top- and bottom-layer schedules.
- [x] Enforce cover, enclosure, aggregate-dependent clear spacing, layer depth,
      and a conservative transverse distribution limit.
- [x] Size an orthogonal crack-control grid using the AREMA 0.003 ratios and
      `min(d/4, 12 in)` spacing ceiling.
- [x] Check section-level compatibility among cover, continuous tie steel,
      crack-control steel, aggregate spacing, layer spacing, hooks, and anchorage.
- [x] Calculate available end anchorage from extended-strut/tie intersections.
- [x] Implement AREMA 2.14 straight tension development.
- [x] Implement standard 90/180-degree hook development, geometry, and fit;
      automatically use a standard hook when straight development fails.
- [x] Exclude headed/mechanical anchors at the user's direction.
- [x] Treat STM longitudinal ties as continuous and unspliced under AREMA
      2.22.3e; retain Class A/B lap calculations for non-tie applications.
- [x] Use full-length, uncurtailed STM ties as the default.

## Optional enhancements and research backlog

These items may improve confidence, flexibility, or research value, but should
not delay the simple production workflow.

### Load and boundary flexibility

- [ ] Make a continuous cap-beam reaction analysis the normal vertical-load
      workflow. Model the cap continuously over support centerlines with one
      pin and all remaining supports as vertical rollers; calculate reactions
      separately for every load combination and apply the loads and reactions
      as prescribed STM boundary forces.
- [ ] Verify the continuous-beam reaction implementation with hand-solvable
      determinate and indeterminate beams, the TxDOT 5-5253-01-1 Figure 4.10
      five-column reactions, force/moment equilibrium, and sensitivity to cap
      EI. The STM topology objective must not redistribute the reactions.
- [ ] Report the reaction-analysis assumptions and provenance: support model,
      support centerlines, cap EI basis, neglected settlement/foundation
      flexibility, and the load combination associated with each reaction set.
- [ ] Provide optional named AREMA load-combination templates and metadata.
      Users may instead supply already factored project load cases.
- [ ] Support prescribed pile/column reactions imported from a compatible
      foundation, continuous-beam, or frame model. This is required for the
      TxDOT 5-5253-01-1 Figure 4.10 validation because the STM topology
      objective must not select the reactions of the indeterminate five-support
      cap.
- [ ] Accept general lateral actions through existing force inputs without
      requiring the tool to generate braking, nosing, wind, or train loads.
- [ ] Add arbitrary interface orientation and local-to-global action transforms
      when a real project requires them.

### Continuum guidance

- [ ] Correct the final-topology/final-displacement mismatch in `run_beso`.
- [ ] Review soft-kill sensitivity against the selected BESO paper.
- [ ] Score discrete candidates against principal-stress direction and magnitude.
- [ ] Compare optimized members with FEM stress trajectories.
- [ ] Add mesh and optimization-parameter sensitivity studies.

### Additional external benchmarks

- [x] Create a source-traceable FHWA benchmark catalog and notebook.
- [x] Reproduce the primary load path and statics of FHWA Design Example 1.
- [x] Encode and automatically generate the published FHWA Example 2 topology.
- [x] Constrain frame-boundary branches by axial force and moment resultants.
- [x] Generate full axial, shear, and moment boundary resultants.
- [x] Derive boundary tie force from equilibrium after fixing its centroid.
- [x] Encode and recover the FHWA Example 3 global STM.
- [x] Plot Example 3 candidates, selected members, rejected alternatives, and
      force comparisons.
- [x] Benchmark published tie steel, nodal geometry, anchorage, nodal-face
      capacities, strut resistance, reinforced-strut steel, intermediate values,
      and final demand/capacity ratios from FHWA Example 1.
- [ ] Validate the production notebook against the global STM in Chapter 4 of
      TxDOT Report 5-5253-01-1 using the Figure 4.10 loads, support reactions,
      geometry, and member forces. Exclude the split-node local column-bearing
      STMs until the double-node capability above is implemented.
- [ ] Reproduce an INDOT STEP pier-cap example if it adds a materially different
      verification case.
- [ ] Compare with published pile-cap experiments where applicable.

## Outside the scope of this tool

These are project-design, detailing, or separate-analysis responsibilities. They
must not appear as unresolved failures of an otherwise complete 2D STM analysis.

- Generate railroad loads from train configuration or determine which project
  load combinations are legally applicable.
- Perform refined global frame, support-settlement, or soil-structure interaction
  analysis. The normal tool may calculate reactions using the documented
  continuous-beam pin/roller idealization or accept reactions supplied by a
  refined analysis.
- Design bearings, piles, shafts, footings, or their reinforcement.
- Produce reinforcing plans, shop drawings, fabrication schedules, or bar lists.
- Determine final three-dimensional bar positions or detect every physical bar
  clash. The tool reports section-level spacing, anchorage, and hook-fit checks.
- Resolve fabrication, shipping-length, erection, or field-placement constraints.
- Select exposure class, durability requirements, or project-specific cover.
  The user confirms or changes the visible default cover input.
- Replace independent engineering review and design approval.
- Build a general-purpose three-dimensional ground-structure solver merely to
  support this two-dimensional pier-cap workflow.

## Separate future project: polygonal sections and local STM generation

This work is deliberately separated from the pier-cap milestone. The cap tool
should not require users to define or mesh arbitrary polygons.

- [ ] Define polygonal concrete boundaries, voids, bearing faces, and
      reinforcement zones.
- [ ] Generate local cross-sectional candidates inside arbitrary polygons.
- [ ] Encode the FHWA Example 3 ledge/hanger local models as benchmarks.
- [ ] Couple local-model resultants to the global cap STM without merging their
      input schemas.
- [ ] Reuse the equilibrium solver, force bounds, topology metrics, benchmark
      framework, and visualization utilities.
- [ ] Consider FHWA Design Example 4 only as part of a separately scoped 3D tool.

## Current limitations to report

- The model is two-dimensional.
- Finite bearing and pile/shaft faces are represented, but their forces are
  applied as centroid resultants rather than distributed contact response.
- Interior interface geometry and capacity use a conservative continuous-tie,
  midpoint-tributary policy without confinement or fan-spreading enhancement.
- All load combinations use one pruned physical candidate structure; force
  reversals are explicitly reported and designed for both signs.
- AREMA 2025 face-specific nodal factors and Article 2.30.2b STM resistance
  factors are implemented and reported with the results.
- A selected load path is statically admissible, not automatically code-compliant.
