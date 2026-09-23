# Tie development and anchorage

## Governing requirement available in the supplied excerpts

The user-supplied 2025 AREMA STM provisions require tie reinforcement to transfer
its force into the nodal regions and refer development design to Articles 2.14
through 2.21. The supplied 2014 AASHTO STM excerpt similarly states that the tie
force must be developed at the inner face of the nodal zone and permits specified
embedment lengths, hooks, or mechanical anchorage, but refers the calculation to
Article 5.11.

The reference folder now includes AREMA 2025 Sections 2.14 through 2.21.
Straight deformed-bar tension development is implemented from Section 2.14 and
Eq. 2-8.1 using US customary units. The implementation applies the 12-inch
minimum and exposes the top-bar, lightweight-concrete, reinforcement-confinement,
excess-reinforcement, and epoxy-coating factors separately for review. The
combined top-bar and epoxy factor is capped at 1.7. The optional excess-steel
reduction is off by default for STM ties.

## Implemented geometry

`calculate_tie_end_anchorage_geometry` automatically:

- identifies the first two and last two nodal tributaries of a continuous tie;
- accepts the actual extended-strut/tie intersection as the final inner critical
  section, retaining the midpoint only as an explicit preliminary fallback;
- places the longitudinal bar end inside clear cover and the enclosing
  crack-control bar;
- calculates the available length between the critical section and bar end; and
- compares the available length with a governing required length when supplied.

For the current demonstration schedule, the extended-boundary lengths are:

| Layer | End | Available length |
|---|---:|---:|
| Top longitudinal tie | Left | 9.56 in |
| Top longitudinal tie | Right | 18.56 in |
| Bottom longitudinal tie | Left | 42.06 in |
| Bottom longitudinal tie | Right | 51.06 in |

For the current demonstration, the compact top end zones make the former 4-#6
schedule slightly deficient even with a hook. The anchorage-aware schedule uses
6-#5 instead. AREMA 2.17 requires 8.49 inches for its standard 90-degree hooks;
the 9.56- and 18.56-inch available lengths pass. The bottom 5-#5 layer requires
16.10 inches straight and passes at both ends.

The production notebook now supplies the calculated AREMA 2.14 straight-bar
length to both ends of each common longitudinal layer. Its current assumptions
are normal-weight concrete, uncoated reinforcement, credit for the selected
transverse crack-control grid, and no excess-steel reduction. Each end therefore
reports `OK` or `NG`. The anchorage type remains recorded so future hooked,
headed, or project-approved mechanical alternatives can be audited.

AREMA Sections 2.17 and 2.4 support the standard-hook calculation and detailing
geometry. Both top ends use standard 90-degree #5 hooks and pass the longitudinal
and transverse-fit checks. The current cover reduction is
applied; the transverse-confinement reduction is not, because the 4.5-inch grid
spacing exceeds 3 bar diameters. Headed and mechanical anchors are intentionally
outside the current project scope.

## Splice policy

AREMA 2.22.3 defines Class A as `1.0 ld` only when at least twice the required
steel is present throughout the splice and no more than half the bars are
spliced within the lap length. Otherwise Class B is `1.3 ld`; both have a
12-inch minimum. These calculations are implemented for non-tie applications.

Article 2.22.3e requires splices in tension tie members to be full welded or
full mechanical connections. Because those connection types are not desired,
the longitudinal STM ties are scheduled as continuous, unspliced bars. The
current cap is 201 inches (16.75 feet) long, so each layer can be detailed as
continuous bars subject to the final bar list, transport limits, and fabricator
confirmation.

The production notebook envelopes the extended nodal-zone/strut intersections
over every analyzed combination. Final design must still verify the input code
edition and factors, exposure cover, coatings, lightweight-concrete assumptions,
and the completed three-dimensional reinforcing drawing.
