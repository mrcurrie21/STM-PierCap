# Pier-Cap Analysis Architecture

## Decision

Use typed Python domain objects for canonical analysis inputs, NumPy-backed
solver objects for calculations, and normalized tables for notebook review and
export. Keep Jupyter notebooks as thin interactive clients. Do not introduce a
database until persistent multi-project or multi-user requirements justify it.

## Intended data flow

```text
Notebook or script
    -> PierCapModel and typed child objects
    -> validation and solver orchestration
    -> ground-structure and design calculations
    -> normalized record tables
    -> optional pandas DataFrames
    -> plots, CSV/Excel/JSON, and future reports
```

## Responsibilities

- `stm_solver.pier_cap`: validated input objects and top-level orchestration.
- Numerical modules: geometry, equilibrium, and design calculations using
  explicit arguments and NumPy arrays.
- `stm_solver.tables`: normalized records and optional DataFrame conversion.
- Notebooks: input editing, calling package APIs, reviewing tables, and plots.
- Tests and benchmarks: engineering rules, numerical behavior, and published
  example comparisons.

Analysis logic must not exist only in notebook cells. New calculations belong
in package modules and must have tests before the notebook consumes them.

## Compatibility and migration

Existing dictionary inputs remain supported while notebooks migrate. New code
should prefer `PierCapModel`, `BearingLoad`, `FoundationSupport`, and
`PierCapGeometry`. Avoid a large rewrite: migrate one input or result boundary
at a time and retain regression coverage.

DataFrames are presentation and interchange objects, not the numerical source
of truth. Stable IDs relate loads, supports, nodes, members, faces, tributaries,
load combinations, and checks. Units remain explicit in documentation and
field descriptions; a formal unit system may be added separately.

## Database threshold

JSON plus CSV or Excel export is sufficient for the current single-analysis
workflow. Consider SQLite or a service database only when the project requires
several persistent projects or alternatives, revision history, cross-analysis
queries, audit records, concurrent users, or application integration. If that
happens, map the existing normalized records to database tables rather than
placing database concerns inside the solver.

## Near-term migration sequence

1. Build new features against typed domain objects.
2. Move load components and combinations from notebook functions into package
   objects.
3. Add normalized result tables for nodal subdivisions and design checks.
4. Migrate the production notebook to the typed API without changing its saved
   engineering inputs.
5. Add JSON persistence and CSV/Excel export.
