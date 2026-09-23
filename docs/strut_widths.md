# Strut-width calculation basis

The current implementation uses the node-face geometry shown in the user-supplied
2025 AREMA Manual for Railway Engineering, Chapter 8, Article 2.42:

- Figure 8-2-6 defines the bearing face, back face, and strut-to-node interface.
- For the subdivided CCC geometry, the projected interface dimension is
  `a*lb*sin(theta_s) + ha*cos(theta_s)`. In the software, `a*lb` is the finite
  face tributary width assigned to the resolved strut force.
- Figure 8-2-7 shows the physical strut extending between the interfaces of its
  two nodal zones.
- Article 2.42.3.d(1) requires the effective node-face area to follow the nodal
  details and out-of-plane dimensions. It also permits the CCT back-face height
  to extend twice the distance from the exterior surface to the longitudinal
  tie centroid when the strut is anchored by reinforcement.

`calculate_strut_width_profiles` therefore maps each constructed interface to
the corresponding compression-member end. When both ends are available, it
reports their minimum as the controlling prismatic screen width and permits
linear interpolation between the end dimensions. Equal end dimensions are
labelled `prismatic`; unequal dimensions are labelled `tapered` only as a
geometric end-width description.

The function deliberately reports `partial` or `missing` when an end interface
has not been constructed. It does not substitute the former assumed width.
Likewise, end-width interpolation does not establish whether a strut is
bottle-shaped or fan-shaped and does not replace a transverse-splitting or
crack-control reinforcement check.

The supplied pages do not uniquely define arbitrary interior nodal faces from
centerline forces alone. The production notebook therefore records the following
preliminary, reviewable policy rather than hiding it in the solver:

- longitudinal reinforcement is declared continuous even when the load-path LP
  omits a zero-force chord segment;
- each interior effective tie face extends to the midpoints between adjacent
  same-layer nodes, with the physical cap ends used at the first and last node;
- the back-face depth is twice the distance from the exterior surface to the
  longitudinal reinforcement centroid;
- transverse compression members on opposite sides of the tie are subdivided
  as separate face sets; and
- compression members parallel to the tie terminate on the rectangular nodal
  region's side face, whose interface width is the back-face depth.

This policy completes both end widths for every compression member in the two
demonstration combinations. It remains an engineering assumption requiring
project review, especially where a real reinforcement cutoff, anchorage zone,
nonhorizontal tie, CTT node, or nonrectangular interior node invalidates it.
