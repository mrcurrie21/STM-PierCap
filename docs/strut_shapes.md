# Strut-shape classification

The classification implementation follows the terminology in FHWA-NHI-130126
and keeps nodal geometry separate from stress-field evidence.

- A **prismatic** strut has equal end widths and no indicated midspan expansion.
- A **bottle-shaped** strut must have a supplied midspan width greater than both
  nodal-interface widths. This follows the FHWA glossary definition that a
  bottle-shaped strut is wider at mid-length than at its ends.
- A **fan-shaped** strut must be explicitly designated as the resultant of a
  distributed fan compression field. FHWA Figures 1-9 and 1-10 illustrate this
  behavior spreading between concentrated resultants and distributed tie steel.
- A complete profile with unequal end widths but no mid-field or fan evidence is
  reported as **tapered**. This is a geometric description, not a claim that the
  physical stress field is prismatic, bottle-shaped, or fan-shaped.

`classify_strut_shape` handles one complete profile. `classify_strut_shapes`
accepts reviewed `midspan_widths` and `fan_member_ids` keyed by member ID and
rejects evidence for unknown members. Each result records its basis, expansion
ratio, and whether further field evidence is required.

The production notebook currently provides empty evidence maps. Its prismatic
labels therefore arise only from equal calculated ends, while unequal-end
members remain tapered and explicitly flagged for continuum or detailing review.
This prevents a discrete centerline STM from manufacturing bottle or fan behavior
that has not actually been demonstrated.

## Adopted simplified design policy

The production design path does not depend on resolving those optional field
labels. It uses the minimum calculated nodal-interface width for compression
capacity, treats every non-prismatic member as bottle-shaped for conservative
detailing, and takes no fan-spreading credit. Orthogonal crack-control steel is
then provided throughout the applicable D-region in both directions.

For the current 42-inch-wide cap with a 27-inch effective depth, two legs of No. 5
reinforcement at 4.5 inches in each direction provide a ratio of 0.0033. The
spacing is below both the ratio-controlled spacing and the `min(d/4, 12 in)`
ceiling. Final drawings must still coordinate these bars with cover, primary tie
steel, laps, and congestion.
