# TxDOT Five-Column Bent Global STM Validation

This validation case uses Chapter 4, Example 1, of TxDOT Report
5-5253-01-1, *Strut-and-Tie Model Design Examples for Bridges*. The example is
a constant-depth, five-column bent cap with the applied loads, reactions,
global STM geometry, and global member forces summarized in Figure 4.10.

## Validation boundary

The first validation milestone is intentionally limited to the **global STM**
shown in Figure 4.10. It will compare:

- cap and global STM geometry;
- applied-load locations and magnitudes from Figure 4.10;
- the five published column reactions;
- global STM topology and member forces;
- global longitudinal-tie demands; and
- nodal checks away from columns only when the published nodal geometry remains
  consistent with the global STM.

The milestone does **not** reproduce or score the local column-bearing nodal
submodels. In the report, column nodes such as JJ and EE are subdivided, the
column reaction is distributed among multiple bearing-face nodes, and adjoining
strut angles are revised before local nodal strength checks are performed.
Checks at adjacent non-column nodes that depend on those revised angles are also
outside the first milestone and will be identified as local-model dependent.

Supporting split/double column nodes and equilibrium-preserving transfer between
the global and local STMs is recorded as future work in the project `TODO.md`.

## Production-code policy

The production notebook and analysis modules remain unchanged while the
published global case is reproduced. If the comparison indicates that a
production-analysis change may be warranted, validation work will stop for
engineering review before any such change is made.

## Current result

The input-adjusted production notebook solves with a negligible equilibrium
residual, but its ground-structure objective selects reactions that differ
materially from the continuous-beam reactions published by TxDOT. The resulting
automatic topology and member forces are therefore not a like-for-like
reproduction of Figure 4.10. A prescribed-reaction input path is needed before
the end-to-end global comparison can pass. No production code was changed.

Independent same-basis checks confirm the published global joint equilibrium,
longitudinal and vertical tie calculations, and the critical non-column girder
bearing calculation. Published strut-interface checks at non-column nodes P, R,
and V depend on angles revised after subdivision of a column node, so they are
deferred under the agreed global-only scope.

## Artifacts

- `txdot_global_stm_validation.ipynb` - executed production-notebook copy.
- `txdot_global_stm_validation.html` - portable notebook output.
- `benchmark_results.html` - concise validation report.
- `benchmark_results.md` and `benchmark_results.json` - reviewable result data.
- `prepare_notebook.py` - reproducibly creates the notebook copy.
- `run_validation.py` - reproducibly creates the comparison reports.

## Source

- `sources/TxDOT_5-5253-01-1_Strut-and-Tie_Model_Design_Examples.pdf`
- Chapter 4 begins on report page 59 (PDF page 77).
- Figure 4.10 is on report page 71 (PDF page 89).
