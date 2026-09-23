# Automatic minimum reinforcement layout

The production notebook generates a reviewable minimum reinforcement schedule
from the solved STM. Users enter geometry, materials, and loads; standard bar
counts and spacing do not have to be selected manually.

## Longitudinal ties

`design_tie_bar_layout` calculates the required steel area from the tie force and
searches a configurable set of standard bars. A candidate must:

- provide at least the required steel area;
- fit within the cap width after clear cover and the crack-control enclosure;
- provide clear spacing of at least the greatest of 1.5 inches, 1.5 bar
  diameters, and twice the specified maximum aggregate size;
- keep transverse bar distribution at or below 12 inches; and
- fit in no more than two layers within the calculated tie-zone depth.

The returned record exposes every assumption. The notebook first retains the
minimum layout for each STM segment, then envelopes the demand into one common
top longitudinal layout and one common bottom longitudinal layout.

For the current demonstration, the 0.75-inch maximum aggregate and compact
end-anchorage geometry lead to these common schedules:

- top longitudinal tie: 6-No. 5, one layer, `As = 1.86 in^2`;
- bottom longitudinal tie: 5-No. 5, one layer, `As = 1.55 in^2`; and
- orthogonal crack-control grid: two-leg No. 5 at 4.5 inches vertically and
  horizontally.

The primary longitudinal bars are not credited toward the separate crack-control
grid, which is conservative.

## Cage review and remaining project review

The notebook now checks longitudinal and crack-grid clear spacing against the
specified aggregate, vertical layer spacing, selected hook projection against
the available cap depth, and final anchorage status. Both current layer cages
pass. STM ties are full-length and uncurtailed, so lap and curtailment conflicts
do not apply.

The generated schedule is still a calculation layout, not a reinforcing drawing.
The engineer must confirm exposure-dependent cover and perform a final 3D
placement/shop-drawing review for local pile, bearing, hook, and crossing-bar
conflicts. Project criteria remain explicit optional inputs.
