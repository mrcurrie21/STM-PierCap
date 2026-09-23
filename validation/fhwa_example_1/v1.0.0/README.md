# FHWA Example 1 production-path validation package

Package version: **1.0.0**

This folder preserves the source and comparison definition needed to run FHWA
Design Example 1 through the same production pier-cap analysis path used by
`notebooks/pier_cap_design.ipynb`.

## Why the folder uses `v1.0.0`

The folder version identifies the validation package: source interpretation,
input mapping, comparison quantities, and tolerances. It is intentionally not a
Git commit. A commit identifies one repository state but is difficult to read,
changes when this documentation is committed, and is not a useful long-term
name. Git provenance is recorded in `manifest.json` and in generated reports.

Increment:

- patch for documentation or tolerance clarification that does not change the
  engineering interpretation;
- minor for added comparison quantities or a backward-compatible input update;
- major when source interpretation, model mapping, or acceptance criteria
  change materially.

## Contents

- `sources/FHWA-NHI-13-0126_Strut-and-Tie_Modeling_Design_Examples.pdf` - the
  official downloaded solved-example manual.
- `manifest.json` - source URL, checksum, relevant pages, and repository state.
- `published_reference.toml` - frozen Example 1 values used for comparisons.
- `comparison_plan.md` - production-path scope, mappings, comparisons, and
  acceptance rules.
- `fhwa_example_1_production_validation.ipynb` - the executed production
  notebook populated with Example 1 inputs. Only its designated input cell
  differs from the production notebook code.
- `fhwa_example_1_production_validation.html` - HTML export of that executed
  notebook.
- `production_comparison.html`, `.md`, and `.json` - comparison of executed
  production results with the published FHWA values and documented basis
  differences.
- `benchmark_results.md` and `benchmark_results.json` - generated results for
  the source-backed Example 1 topology/force benchmark, with computed values,
  published values, tolerances, and status.
- `run_validation.py` - regenerate the benchmark comparison report.
- `create_validation_notebook.py` - regenerate the Example 1 notebook copy from
  the current production notebook template.
- `run_production_validation.py` - execute the copied notebook from the
  repository root and generate its HTML export.
- `build_production_comparison.py` - regenerate the production/FHWA comparison.

The active executable benchmark currently remains in
`benchmarks/fhwa_nhi_130126.toml`. This package is the frozen documentation set;
future implementation should load or verify against this package so the two
cannot drift silently.

## Integrity check

From the repository root:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath `
  'validation\fhwa_example_1\v1.0.0\sources\FHWA-NHI-13-0126_Strut-and-Tie_Modeling_Design_Examples.pdf'
```

Expected SHA-256:

`BE2F93DD890FC1CDD4128109A32ACECDD1878313E1FAE05F8E27F9AF447C7A8D`

## Reproduction target

The target is not merely to call benchmark-only equations. The published input
is to be passed through the shared production analysis function, producing the
normal normalized tables and HTML report. A validation appendix will then show
published, computed, computed/published, percentage difference, tolerance, and
status for every accepted comparison.

## Regenerate benchmark results

From the repository root:

```powershell
python validation\fhwa_example_1\v1.0.0\run_validation.py
```

To regenerate all production artifacts from the repository root:

```powershell
python validation\fhwa_example_1\v1.0.0\create_validation_notebook.py
python validation\fhwa_example_1\v1.0.0\run_production_validation.py
python validation\fhwa_example_1\v1.0.0\build_production_comparison.py
```

The production run validates equilibrium, the FHWA-approved symmetric direct
strut topology, tie demand and reinforcement, final CCC nodal geometry and
capacity, crack-control grids, and anchorage adequacy. Supplemental steel for a
reinforced compression chord remains a documented production feature gap.
