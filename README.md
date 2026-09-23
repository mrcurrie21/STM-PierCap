# Pier-Cap STM

**Production-oriented strut-and-tie modeling for pile-supported concrete bridge caps**

## Overview

Pier-Cap STM provides a focused two-dimensional strut-and-tie workflow for
pile-supported reinforced-concrete bridge caps. It generates a discrete ground
structure, selects statically admissible load paths for multiple load
combinations, performs design and detailing checks, and produces reviewable
calculation outputs.

## Features

- **Ground-Structure Optimization**: Selects an equilibrium-compatible STM from
  discrete candidate members using linear programming
- **Multiple Load Combinations**: Uses one pruned physical structure and
  envelopes force demand, reversals, and detailing requirements
- **Finite External Faces**: Retains bearing and support face geometry for
  external nodal-zone checks
- **Design Checks**: Conservative tie, strut, anchorage, crack-control, and
  nodal-face checks with visible code-profile assumptions
- **Reinforcement Selection**: Automatic bar size/count selection from standard rebar table (#3-#18)
- **Design Reports**: Comprehensive formatted output with D/C ratios and reinforcement summary
- **Traceable Outputs**: Exports normalized JSON, CSV, Excel, Markdown, and HTML
  results with calculation fingerprints and source metadata
- **Imperial Units**: All calculations in kips, inches, and ksi

## Pier-Cap Ground-Structure Workflow

The pier-cap workflow generates a discrete candidate layout and
select a statically admissible strut-and-tie model by linear programming. This
produces an explicitly truss-like load path directly from the modeled cap,
loads, supports, and candidate-member rules.

```python
from stm_solver import BearingLoad, FoundationSupport, PierCapGeometry, PierCapModel
from stm_solver.tables import ground_structure_records, records_to_dataframes

model = PierCapModel(
    geometry=PierCapGeometry(
        length=120.0, width=42.0, depth=36.0,
        top_tie_y=33.0, bottom_tie_y=3.0,
    ),
    loads=(BearingLoad("B1", 60.0, 36.0, -200.0, 12.0),),
    supports=(
        FoundationSupport("P1", 24.0, 0.0, 18.0, restraint="pin"),
        FoundationSupport("P2", 96.0, 0.0, 18.0),
    ),
)

result = model.solve()
tables = records_to_dataframes(ground_structure_records(result))
print(result.truss_model.members)
print(result.member_forces)  # positive=tie, negative=strut
print(result.equilibrium_residual)
print(tables["external_faces"])
```

Optional finite faces are centered on each external resultant. Bearing loads
accept `face_width` or `bearing_width`; pile/shaft supports accept `face_width`
or `diameter` and may set `foundation_type` to `pile` or `shaft`. The force-flow
model still applies the resultant at the face centroid, while retaining face
endpoints for nodal geometry and using the actual width in external-node checks.
Singular external nodes with one compression strut can be constructed with
`construct_external_nodal_zone`. Its projected strut-interface width is checked
against FHWA Design Example 1; multi-strut nodes require explicit subdivision.
`subdivide_external_face` assigns contiguous uniform-pressure tributaries using
normal force components and is benchmarked against the 8.59 in / 16.61 in split
at Node G of FHWA Design Example 3.
The same benchmark verifies the revised tributary-centroid strut axis and both
projected strut-interface widths.
`resolve_member_forces_at_node` combines an explicitly selected adjacent-member
group into one design resultant; its vector and angle are benchmarked against
FHWA Example 3's resolved Strut AA'G.

The workflow establishes force flow and provides design screens.
The production notebook envelopes tie and strut forces across its solved load
combinations, calculates tie steel area and a preferred bar count, screens struts
with an explicitly assumed width, and checks external bearing-face stress. Actual
strut widths, complete nodal geometry, reinforcement placement and anchorage, and
applicable AREMA provisions remain separate design steps.
Pier-cap diagonal web candidates are compression-only by default; diagonal ties
require an explicit future opt-in and reinforcement-path definition. Selected
models can be screened with `find_member_crossings`, which reports unintended
non-nodal intersections.

### Scope boundary

The primary application is longitudinal analysis of pile-supported concrete
bridge caps. Automatic STM generation for arbitrary polygonal cross sections,
including local inverted-tee ledge and hanger models, is intentionally treated
as a separate future project. That project can reuse the candidate-generation,
equilibrium, force-bound, benchmarking, and visualization components developed
for the cap analysis without making polygon input a prerequisite for ordinary
pier-cap models.

For a cap-to-column or cap-to-B-region interface, the frame boundary is modeled
with prescribed force resultants using `optimize_frame_boundary`. Those boundary
resultants are inputs from a compatible sectional or global analysis; they are not
free support reactions. The optimizer then selects the internal D-region STM that
connects applied loads to those interface resultants.

The production-oriented notebook scaffold is
`notebooks/pier_cap_design.ipynb`. It accepts named load components and
user-defined combinations, validates longitudinal geometry, generates one
common candidate structure, prunes members unused by every case, and re-solves
every combination for equilibrium. It reports force reversals, produces one
common reinforcement schedule, checks external and conservative interior nodal
faces, and creates normalized result tables plus a concise calculation summary.
Its example loads are demonstrations only and are not AREMA load combinations.

Normal project inputs are kept in one cell. Consequential assumptions such as
clear cover, aggregate size, coating, concrete weight, preferred bar sizes, and
standard-hook permission remain visible with editable defaults. Derived
reinforcement and nodal quantities are automatic. AREMA 2025 nodal factors from
Article 2.42.3d and Table 8-2-9 are implemented. Article 2.30.2b supplies the
implemented STM resistance factors: 0.70 for compression and 0.90 for
reinforced-concrete tension.

New pier-cap work uses validated objects from `stm_solver.pier_cap` as the
canonical input API and normalized records/DataFrames for review and export.
Notebooks remain interactive front ends; calculation logic belongs in tested
package modules. See `docs/architecture.md` for the package boundaries and the
criteria for introducing a database.

## Project Structure

```
Pier-Cap-STM/
  stm_solver/              # Python package
    __init__.py
    benchmarks.py          # Published benchmark definitions and comparisons
    design_checks.py       # Strut, tie, nodal, anchorage, and detailing checks
    ground_structure.py    # Candidate generation and equilibrium optimization
    pier_cap.py            # Validated production input model
    reporting.py           # Markdown and HTML calculation reports
    tables.py              # Normalized records and file exports
    truss_extract.py       # Shared truss data structures and geometry helpers
    versioning.py          # Version, provenance, and fingerprint metadata
  notebooks/
    pier_cap_design.ipynb  # Production workflow notebook
  benchmarks/              # Source-traceable benchmark catalog
  docs/                    # Engineering basis and workflow documentation
  tests/                   # Curated production test suite
  validation/              # Versioned validation packages and source records
  .github/workflows/ci.yml # GitHub Actions CI
  pyproject.toml           # Build config, ruff, pytest settings
  requirements.txt
```

## Quick Start

### Installation

```bash
git clone <repository-url> pier_cap_stm
cd pier_cap_stm
pip install -e ".[dev,notebook]"
```

### Usage

Open and run the Jupyter notebook:

```bash
jupyter notebook notebooks/pier_cap_design.ipynb
```

Edit the normal project-input cell to define cap geometry, materials, bearings,
foundation supports, load components, combinations, and visible detailing
assumptions. Run all cells to select the load path, perform the checks, and
generate the calculation outputs.

### Running Tests

```bash
pytest tests/ -v
ruff check stm_solver/ tests/
```

## Design Workflow

1. Validate cap geometry, material properties, finite faces, loads, supports,
   and load combinations.
2. Generate the discrete candidate structure and solve nodal equilibrium for
   every combination.
3. Prune unused members, reject non-nodal crossings, and report force reversals
   and model-quality metrics.
4. Envelope tie and strut forces and perform reinforcement, anchorage,
   crack-control, nodal-face, strut-shape, and cage-fit checks.
5. Export the calculation report and normalized technical tables for review.

## References

- AREMA Manual for Railway Engineering (2025), Chapter 8.
- FHWA-NHI-13-012, *Strut-and-Tie Modeling (STM) for Concrete Structures*.

## License

MIT
