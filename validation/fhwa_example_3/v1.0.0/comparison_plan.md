# FHWA Example 3 production comparison plan

## Objective

Run the FHWA Example 3 global inverted-tee cap through the production notebook
without changing its analysis code between project and validation cases.

## Published model mapping

| FHWA concept | Required production representation |
|---|---|
| 47.50-ft cap envelope | General cap geometry with top and lower STM chords |
| Ten cap loads | Named factored point resultants at Nodes B through L |
| Column A interface | Prescribed branches at A-prime and G-prime reproducing axial force, shear, and moment |
| Column B interface | Prescribed branches at L-prime and F-prime reproducing axial force, shear, and moment |
| Global STM | Ground structure generated from the published chord and boundary locations |
| Local ledge STM | Separate future validation; not part of the global notebook run |

## Production issue found and corrected

The production notebook constructs `FoundationSupport` inputs and calls
`optimize_pier_cap_load_cases`. Those supports constrain degrees of freedom and
allow reactions to be solved by the optimizer. Example 3 instead supplies
section resultants from a moment-frame analysis. Their axial force, shear, and
moment must be preserved through multiple boundary branches.

The shared package provided only a single-section action helper and the
production notebook did not expose a frame-boundary mode. Example 3 also puts
loads on both chord levels and uses two column interfaces.

After user approval, `optimize_frame_boundary_load_cases` and an optional
`analysis_mode = 'frame_boundary'` notebook route were added. Reviewed
interface-branch force targets preserve the adjoining-frame resultants. The
existing `analysis_mode = 'pier_cap'` path remains the default.

The force-flow and topology sections run in both modes. Bearing-face, nodal
capacity, reinforcement, and anchorage checks are explicitly skipped in frame
mode because Example 3's global centerline model does not supply the finite
faces and inch-based detailing inputs those checks require.

The validation copy differs from the revised production notebook only in its
designated input cell. It is executed and stored beside its HTML rendering and
the FHWA source PDF.

## Acceptance comparisons

- Applied cap loads and boundary resultants.
- Global equilibrium residual.
- All published global member force signs and magnitudes.
- Candidate topology recall and precision.
- Column-interface axial force, shear, and moment recovery.
- Global member tension/compression sense and force magnitude.
- Explicit separation of local ledge/hanger checks from the global model.

## Result

All 29 published members pass. Candidate topology recall and precision are
both 100%, all fixed interface branches pass the 3% boundary tolerance, the
remaining members pass the 22% published-example tolerance, and global
equilibrium residual is 2.27e-13 kip.
