# FHWA Example 3 production-path validation package

Package version: **1.0.0**

This folder preserves the source, published global STM, and compatibility
assessment for FHWA Design Example 3, an inverted-tee moment-frame straddle
bent cap.

## Current status

**PASS.** The production notebook was extended, with approval, to support an
optional frame-boundary analysis mode while retaining the pile-supported mode
as its default. The executed validation copy uses only Example 3 inputs and
calls that production solver path. All 29 published global members pass the
source-defined tolerances; the equilibrium residual is 2.27e-13 kip.

The comparison covers the global STM. FHWA's separate local ledge and hanger
models are intentionally outside this validation slice.

The Figure 3-10 diagonal labels were visually reviewed in their proper page
orientation. The frozen reference uses AG = -802.0 kip, GB = -1,078.1 kip,
CH = -1,010.5 kip, CJ = -41.8 kip, and EL = -1,330.5 kip. The notebook plot
limits are derived from all truss nodes so the column-interface supports remain
visible.

## Contents

- `FHWA-NHI-13-0126_Strut-and-Tie_Modeling_Design_Examples.pdf` - official
  FHWA solved-example manual, copied beside the validation artifacts.
- `manifest.json` - source identity, checksum, and relevant pages.
- `published_reference.json` - frozen Example 3 nodes, members, loads,
  boundary branches, and published forces from the benchmark catalog.
- `benchmark_results.json`, `.md`, and `.html` - generated prescribed-topology
  and production-path comparison results.
- `fhwa_example_3_production_validation.ipynb` - executed production notebook
  copy with Example 3 inputs.
- `fhwa_example_3_production_validation.html` - rendered notebook output.
- `fhwa_example_3_production_validation.pdf` - user-supplied print used to
  identify the original cropping issue; it predates the corrected HTML.
- `comparison_plan.md` - final scope, mapping, and acceptance criteria.
- `run_validation.py` - regenerates the numerical comparison.
- `prepare_notebook.py` - records how the validation copy was prepared.

## Regenerate the current benchmark

From the repository root:

```powershell
python validation\fhwa_example_3\v1.0.0\run_validation.py
```
