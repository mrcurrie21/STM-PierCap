"""AASHTO LRFD Section 5.8.2 strut-and-tie design checks."""

from dataclasses import dataclass, replace

import numpy as np

from stm_solver.ground_structure import ExternalFace

# Standard rebar table (US customary)
REBAR_TABLE = {
    3:  {'db': 0.375, 'Ab': 0.11},
    4:  {'db': 0.500, 'Ab': 0.20},
    5:  {'db': 0.625, 'Ab': 0.31},
    6:  {'db': 0.750, 'Ab': 0.44},
    7:  {'db': 0.875, 'Ab': 0.60},
    8:  {'db': 1.000, 'Ab': 0.79},
    9:  {'db': 1.128, 'Ab': 1.00},
    10: {'db': 1.270, 'Ab': 1.27},
    11: {'db': 1.410, 'Ab': 1.56},
    14: {'db': 1.693, 'Ab': 2.25},
    18: {'db': 2.257, 'Ab': 4.00},
}


def arema_2025_stm_resistance_factors():
    """Return AREMA 2025 Article 2.30.2b STM resistance factors."""
    return {
        "compression": 0.70,
        "reinforced_concrete_tension": 0.90,
        "prestressed_concrete_tension": 1.00,
        "anchorage_zone_compression": 0.80,
        "anchorage_zone_tension_steel": 1.00,
    }


def arema_2025_nodal_stress_factors(fc_prime, *, crack_control=True):
    """Return face-specific AREMA 2025 Article 2.42.3d efficiency factors.

    Stress input is ksi. With the required Article 2.42.3e crack-control grid,
    Table 8-2-9 uses 0.85 for CCC bearing/back faces, 0.70 for CCT
    bearing/back faces, ``k1`` for CTT bearing/back faces, and ``k1`` bounded
    between 0.45 and 0.65 at every strut-to-node interface, where
    ``k1 = 0.85 - f'c/20`` in ksi units. Without that grid, Article 2.42.3d(2)
    limits every face to 0.45.
    """
    fc_prime = float(fc_prime)
    if not np.isfinite(fc_prime) or not 0.0 < fc_prime <= 10.0:
        raise ValueError("AREMA STM fc_prime must be in the interval (0, 10] ksi")
    if not crack_control:
        return {
            zone: {face: 0.45 for face in (
                "bearing", "back", "tie_boundary", "opposite_boundary",
                "strut_interface",
            )}
            for zone in ("CCC", "CCT", "CTT")
        }
    k1 = 0.85 - fc_prime / 20.0
    interface = min(0.65, max(0.45, k1))
    return {
        "CCC": {
            "bearing": 0.85, "back": 0.85,
            "tie_boundary": 0.85, "opposite_boundary": 0.85,
            "strut_interface": interface,
        },
        "CCT": {
            "bearing": 0.70, "back": 0.70,
            "tie_boundary": 0.70, "opposite_boundary": 0.70,
            "strut_interface": interface,
        },
        "CTT": {
            "bearing": k1, "back": k1,
            "tie_boundary": k1, "opposite_boundary": k1,
            "strut_interface": interface,
        },
    }


@dataclass
class StrutCheck:
    """Result of AASHTO strut capacity check."""
    member_id: int
    force: float          # kip (negative = compression)
    strut_width: float    # in
    strut_area: float     # in^2
    fcu: float            # ksi (limiting compressive stress)
    capacity: float       # kip (phi * fcu * Acs)
    dc_ratio: float       # demand/capacity
    status: str           # 'OK' or 'NG'
    phi: float = 0.75     # AASHTO resistance factor for struts


@dataclass(frozen=True)
class StrutWidthProfile:
    """Calculated in-plane widths at the two nodal ends of a strut.

    Widths are measured normal to the member axis. A missing width means that
    no compatible nodal interface has yet been constructed at that end.
    """

    member_id: int
    node_i: int
    node_j: int
    width_i: float | None
    width_j: float | None
    controlling_width: float | None
    maximum_width: float | None
    profile_type: str
    status: str


@dataclass(frozen=True)
class StrutShapeClassification:
    """Auditable geometric classification of one complete strut profile."""

    member_id: int
    shape: str
    width_i: float
    width_mid: float | None
    width_j: float
    maximum_width: float
    expansion_ratio: float
    basis: str
    field_evidence_required: bool


@dataclass(frozen=True)
class ConservativeStrutDesign:
    """Simplified design treatment adopted for one complete strut profile."""

    member_id: int
    observed_shape: str
    design_shape: str
    capacity_width: float
    fan_spreading_credit: bool
    orthogonal_crack_control_required: bool
    basis: str


@dataclass(frozen=True)
class CrackControlGrid:
    """One direction of an AREMA-style orthogonal crack-control grid."""

    direction: str
    required_ratio: float
    member_width: float
    effective_depth: float
    spacing_limit: float
    bar_size: int | None
    legs: int | None
    steel_area_per_spacing: float
    selected_spacing: float
    provided_ratio: float
    status: str


@dataclass
class TieCheck:
    """Result of AASHTO tie reinforcement check."""
    member_id: int
    force: float          # kip (positive = tension)
    As_required: float    # in^2
    As_provided: float    # in^2
    bar_size: int         # rebar number (#3-#18)
    n_bars: int           # number of bars
    dc_ratio: float       # demand/capacity
    status: str           # 'OK' or 'NG'
    phi: float = 0.90     # AASHTO resistance factor for ties
    fy: float = 60.0      # ksi


@dataclass(frozen=True)
class TieBarLayout:
    """Automatically selected longitudinal tie-bar arrangement."""

    as_required: float
    as_provided: float
    bar_size: int
    bar_count: int
    layers: int
    bars_per_layer: tuple
    section_width: float
    tie_zone_depth: float
    clear_cover: float
    enclosure_bar_size: int
    minimum_clear_spacing: float
    maximum_aggregate_size: float | None
    required_transverse_clear_spacing: float
    minimum_layer_clear_spacing: float
    maximum_transverse_spacing: float
    transverse_center_spacing: float
    transverse_clear_spacing: float
    layer_clear_spacing: float | None
    status: str


@dataclass(frozen=True)
class ReinforcementCageReview:
    """Section-level constructability screen for one longitudinal tie cage."""

    layer: str
    required_transverse_clear_spacing: float
    provided_transverse_clear_spacing: float
    required_layer_clear_spacing: float
    provided_layer_clear_spacing: float | None
    required_crack_control_clear_spacing: float
    provided_crack_control_clear_spacing: float
    available_hook_depth: float
    maximum_hook_projection: float | None
    anchorage_status: str
    status: str
    basis: str


@dataclass(frozen=True)
class TieAnchorageGeometry:
    """Available end-anchorage length measured from a nodal critical section."""

    layer: str
    end: str
    end_node_coordinate: float
    adjacent_node_coordinate: float
    critical_section_coordinate: float
    bar_end_coordinate: float
    available_length: float
    required_development_length: float | None
    anchorage_type: str
    status: str
    basis: str


@dataclass(frozen=True)
class TensionDevelopmentLength:
    """AREMA 2.14 straight deformed-bar development calculation."""

    bar_size: int
    bar_diameter: float
    fy: float
    fc_prime: float
    basic_length: float
    top_bar_factor: float
    lightweight_factor: float
    confinement_factor: float
    excess_reinforcement_factor: float
    epoxy_factor: float
    combined_top_epoxy_factor: float
    calculated_length: float
    minimum_length: float
    required_length: float
    basis: str


@dataclass(frozen=True)
class StandardHookDevelopment:
    """AREMA 2.17 development and 2.4 geometry for a standard hook."""

    bar_size: int
    hook_angle: int
    bar_diameter: float
    inside_bend_diameter: float
    tail_extension: float
    transverse_projection: float
    basic_length: float
    epoxy_factor: float
    cover_factor: float
    confinement_factor: float
    excess_reinforcement_factor: float
    lightweight_factor: float
    calculated_length: float
    minimum_length: float
    required_length: float
    basis: str


@dataclass(frozen=True)
class TensionLapSplice:
    """AREMA 2.22.3 tension lap-splice classification and length."""

    bar_size: int
    development_length: float
    splice_class: str
    multiplier: float
    calculated_length: float
    minimum_length: float
    required_length: float
    permitted_for_tension_tie_member: bool
    basis: str


@dataclass
class NodalZoneCheck:
    """Result of AASHTO nodal zone capacity check."""
    node_id: int
    zone_type: str        # 'CCC', 'CCT', or 'CTT'
    max_force: float      # kip (maximum force at node)
    bearing_area: float   # in^2
    fcu_node: float       # ksi (limiting nodal zone stress)
    capacity: float       # kip
    dc_ratio: float       # demand/capacity
    status: str           # 'OK' or 'NG'
    phi: float = 0.75


@dataclass(frozen=True)
class NodalFaceCheck:
    """Demand and capacity of one face of a constructed nodal zone."""

    node_id: int
    group_label: str
    zone_type: str
    face_type: str
    demand: float
    face_width: float
    area: float
    stress_factor: float
    confinement_factor: float
    fcu: float
    capacity: float
    dc_ratio: float
    status: str
    phi: float


@dataclass(frozen=True)
class NodalZoneGeometry:
    """Projected geometry of a singular external nodal zone.

    Segments are represented by their two global-coordinate endpoints. The
    strut interface is normal to the strut axis and has the projected width
    required to receive the finite bearing and back faces.
    """

    node_id: int
    zone_type: str
    bearing_face: tuple
    back_face_depth: float
    strut_member_id: int
    strut_angle_degrees: float
    strut_interface_width: float
    strut_interface: tuple


@dataclass(frozen=True)
class NodalFaceTributary:
    """Contiguous portion of an external face assigned to one force path."""

    node_id: int
    source_index: int
    parent_kind: str
    label: str
    center: tuple
    start: tuple
    end: tuple
    width: float
    normal_force: float


@dataclass(frozen=True)
class RevisedStrutAxis:
    """Strut axis revised to pass through a face tributary centroid."""

    start: tuple
    end: tuple
    length: float
    angle_degrees: float


@dataclass(frozen=True)
class ResolvedNodalForce:
    """Vector resultant of a selected group of members at one node."""

    node_id: int
    member_ids: tuple
    vector: tuple
    magnitude: float
    angle_degrees: float


@dataclass(frozen=True)
class NodalZoneGroupDefinition:
    """Engineer-reviewed mapping from STM members to one design strut."""

    label: str
    member_ids: tuple
    remote_point: tuple
    zone_type: str


@dataclass(frozen=True)
class NodalZoneGroupGeometry:
    """Resolved geometry for one tributary of a subdivided external node."""

    label: str
    zone_type: str
    member_ids: tuple
    resultant: ResolvedNodalForce
    tributary: NodalFaceTributary
    revised_axis: RevisedStrutAxis
    strut_interface_width: float
    nodal_polygon: tuple
    strut_interface: tuple


@dataclass(frozen=True)
class ExternalNodalZonePlan:
    """Explicit subdivision plan for one finite external face."""

    node_id: int
    back_face_depth: float
    groups: tuple


def calculate_strut_width_profiles(
    truss_model, member_forces, nodal_group_geometries, *,
    force_tolerance=1e-9, width_tolerance=1e-8,
):
    """Assemble calculated strut end widths from constructed nodal interfaces.

    Each interface must belong to one actual truss member. A reviewed group
    that resolves several members into a replacement design strut cannot be
    assigned back to those individual members and is therefore rejected.
    Complete profiles are linearly interpolable between their two interface
    widths; the smaller end is the controlling prismatic design width.
    """
    forces = np.asarray(member_forces, dtype=float)
    if forces.shape != (len(truss_model.members),):
        raise ValueError("member_forces must align with truss_model.members")
    if not np.isfinite(force_tolerance) or force_tolerance < 0.0:
        raise ValueError("force_tolerance must be nonnegative and finite")

    connector_members = set()
    for face in getattr(truss_model, "external_faces", ()):
        nodal_node_id = getattr(face, "nodal_node_id", None)
        if nodal_node_id is None or nodal_node_id == face.node_id:
            continue
        for member_id, member in enumerate(truss_model.members):
            if set(map(int, member)) == {int(face.node_id), int(nodal_node_id)}:
                connector_members.add(member_id)

    widths_by_member = {}
    for geometry in nodal_group_geometries:
        if len(geometry.member_ids) != 1:
            raise ValueError(
                "A resolved multi-member nodal group defines a replacement "
                "design strut; assign it an explicit design-strut identity"
            )
        member_id = int(geometry.member_ids[0])
        if not 0 <= member_id < len(truss_model.members):
            raise ValueError("Nodal geometry references an unknown member")
        if forces[member_id] >= -force_tolerance:
            raise ValueError("Nodal strut geometry references a non-compression member")
        node_id = int(geometry.tributary.node_id)
        if node_id not in truss_model.members[member_id]:
            raise ValueError("Nodal interface is not at an end of its strut member")
        width = float(geometry.strut_interface_width)
        if not np.isfinite(width) or width <= 0.0:
            raise ValueError("Strut interface widths must be positive and finite")
        member_widths = widths_by_member.setdefault(member_id, {})
        if node_id in member_widths and not np.isclose(
            member_widths[node_id], width, atol=width_tolerance, rtol=0.0
        ):
            raise ValueError("A strut end has conflicting nodal interface widths")
        member_widths[node_id] = width

        face_vector = np.asarray(geometry.tributary.end) - np.asarray(
            geometry.tributary.start
        )
        face_direction = face_vector / np.linalg.norm(face_vector)
        face_normal = np.array([-face_direction[1], face_direction[0]])
        polygon = np.asarray(geometry.nodal_polygon, dtype=float)
        center = np.asarray(geometry.tributary.center, dtype=float)
        back_depth = float(np.max(np.abs((polygon - center) @ face_normal)))
        for parallel_id, (ni, nj) in enumerate(truss_model.members):
            if parallel_id in connector_members or parallel_id == member_id:
                continue
            if node_id not in (ni, nj) or forces[parallel_id] >= -force_tolerance:
                continue
            other = int(nj if ni == node_id else ni)
            direction = np.asarray(truss_model.nodes[other]) - np.asarray(
                truss_model.nodes[node_id]
            )
            direction /= np.linalg.norm(direction)
            if abs(float(np.dot(direction, face_direction))) < 1.0 - 1e-8:
                continue
            parallel_widths = widths_by_member.setdefault(parallel_id, {})
            parallel_widths[node_id] = back_depth

    profiles = []
    for member_id, ((node_i, node_j), force) in enumerate(
        zip(truss_model.members, forces)
    ):
        if force >= -force_tolerance or member_id in connector_members:
            continue
        end_widths = widths_by_member.get(member_id, {})
        width_i = end_widths.get(int(node_i))
        width_j = end_widths.get(int(node_j))
        known = [width for width in (width_i, width_j) if width is not None]
        if len(known) == 2:
            controlling = min(known)
            maximum = max(known)
            profile_type = (
                "prismatic" if np.isclose(
                    width_i, width_j, atol=width_tolerance, rtol=0.0
                ) else "tapered"
            )
            status = "complete"
        elif len(known) == 1:
            controlling = None
            maximum = known[0]
            profile_type = "unresolved"
            status = "partial"
        else:
            controlling = maximum = None
            profile_type = "unresolved"
            status = "missing"
        profiles.append(StrutWidthProfile(
            member_id=member_id,
            node_i=int(node_i),
            node_j=int(node_j),
            width_i=width_i,
            width_j=width_j,
            controlling_width=controlling,
            maximum_width=maximum,
            profile_type=profile_type,
            status=status,
        ))
    return tuple(profiles)


def strut_width_at(profile, station):
    """Linearly interpolate a complete end-width profile at ``0 <= station <= 1``."""
    station = float(station)
    if not np.isfinite(station) or not 0.0 <= station <= 1.0:
        raise ValueError("station must be finite and between 0 and 1")
    if profile.status != "complete":
        raise ValueError("Both nodal end widths are required for interpolation")
    return float(profile.width_i + station * (profile.width_j - profile.width_i))


def classify_strut_shape(
    profile, *, midspan_width=None, represents_fan_field=False,
    width_tolerance=1e-8,
):
    """Classify a complete width profile without inventing stress-field evidence.

    FHWA defines a bottle-shaped strut as wider at mid-length than at its ends.
    A fan-shaped label is reserved for an explicitly identified distributed fan
    compression field. Unequal ends alone describe a tapered envelope and are
    insufficient evidence for either label.
    """
    if profile.status != "complete":
        raise ValueError("A complete two-ended width profile is required")
    tolerance = float(width_tolerance)
    if not np.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("width_tolerance must be nonnegative and finite")
    width_i = float(profile.width_i)
    width_j = float(profile.width_j)
    if midspan_width is None:
        width_mid = None
    else:
        width_mid = float(midspan_width)
        if not np.isfinite(width_mid) or width_mid <= 0.0:
            raise ValueError("midspan_width must be positive and finite")

    end_max = max(width_i, width_j)
    end_min = min(width_i, width_j)
    if represents_fan_field:
        shape = "fan-shaped"
        maximum = max(end_max, width_mid or 0.0)
        basis = "explicit distributed fan compression-field designation"
        needs_evidence = False
    elif width_mid is not None and width_mid > end_max + tolerance:
        shape = "bottle-shaped"
        maximum = width_mid
        basis = "midspan width exceeds both nodal-interface widths"
        needs_evidence = False
    elif np.isclose(width_i, width_j, atol=tolerance, rtol=0.0) and (
        width_mid is None
        or np.isclose(width_mid, width_i, atol=tolerance, rtol=0.0)
    ):
        shape = "prismatic"
        maximum = max(end_max, width_mid or 0.0)
        basis = "equal end widths with no midspan expansion"
        needs_evidence = False
    else:
        shape = "tapered"
        maximum = max(end_max, width_mid or 0.0)
        basis = "unequal end widths; bottle/fan field not established"
        needs_evidence = True
    return StrutShapeClassification(
        member_id=profile.member_id,
        shape=shape,
        width_i=width_i,
        width_mid=width_mid,
        width_j=width_j,
        maximum_width=maximum,
        expansion_ratio=maximum / end_min,
        basis=basis,
        field_evidence_required=needs_evidence,
    )


def classify_strut_shapes(
    profiles, *, midspan_widths=None, fan_member_ids=(), width_tolerance=1e-8,
):
    """Classify complete profiles using explicit optional field evidence maps."""
    midspan_widths = {} if midspan_widths is None else dict(midspan_widths)
    fan_member_ids = {int(member_id) for member_id in fan_member_ids}
    profile_ids = {profile.member_id for profile in profiles}
    unknown = (set(midspan_widths) | fan_member_ids) - profile_ids
    if unknown:
        raise ValueError(f"Shape evidence references unknown members: {sorted(unknown)}")
    return tuple(
        classify_strut_shape(
            profile,
            midspan_width=midspan_widths.get(profile.member_id),
            represents_fan_field=profile.member_id in fan_member_ids,
            width_tolerance=width_tolerance,
        )
        for profile in profiles
        if profile.status == "complete"
    )


def apply_conservative_strut_policy(profiles, classifications):
    """Use minimum end width and bottle detailing for every non-prismatic strut."""
    by_member = {item.member_id: item for item in classifications}
    designs = []
    for profile in profiles:
        if profile.status != "complete":
            raise ValueError("Conservative strut policy requires complete profiles")
        if profile.member_id not in by_member:
            raise ValueError("Every strut profile requires a shape classification")
        classification = by_member[profile.member_id]
        design_shape = (
            "prismatic" if classification.shape == "prismatic"
            else "bottle-shaped-conservative"
        )
        designs.append(ConservativeStrutDesign(
            member_id=profile.member_id,
            observed_shape=classification.shape,
            design_shape=design_shape,
            capacity_width=float(profile.controlling_width),
            fan_spreading_credit=False,
            orthogonal_crack_control_required=True,
            basis=(
                "minimum nodal-interface width controls capacity; non-prismatic "
                "struts receive conservative bottle-shaped detailing"
            ),
        ))
    if set(by_member) != {profile.member_id for profile in profiles}:
        raise ValueError("Shape classifications and profiles must reference the same members")
    return tuple(designs)


def design_orthogonal_crack_control_grid(
    member_width, effective_depth, *, bar_size=5, legs=2,
    required_ratio=0.003, absolute_spacing_limit=12.0,
    spacing_increment=0.5,
):
    """Select equal vertical/horizontal grid spacing satisfying AREMA 2.42.3.e."""
    member_width = float(member_width)
    effective_depth = float(effective_depth)
    required_ratio = float(required_ratio)
    absolute_spacing_limit = float(absolute_spacing_limit)
    spacing_increment = float(spacing_increment)
    legs = int(legs)
    if any(not np.isfinite(value) or value <= 0.0 for value in (
        member_width, effective_depth, required_ratio,
        absolute_spacing_limit, spacing_increment,
    )):
        raise ValueError("Crack-control dimensions, ratio, and spacing must be positive")
    if bar_size not in REBAR_TABLE:
        raise ValueError(f"Unknown crack-control bar size: #{bar_size}")
    if legs <= 0:
        raise ValueError("Crack-control grid requires at least one bar leg")

    steel_area = legs * REBAR_TABLE[bar_size]["Ab"]
    spacing_limit = min(effective_depth / 4.0, absolute_spacing_limit)
    ratio_spacing = steel_area / (required_ratio * member_width)
    unrounded_spacing = min(spacing_limit, ratio_spacing)
    selected_spacing = np.floor(unrounded_spacing / spacing_increment) * spacing_increment
    if selected_spacing <= 0.0:
        raise ValueError("Selected bar configuration cannot satisfy the required ratio")
    provided_ratio = steel_area / (member_width * selected_spacing)
    return tuple(
        CrackControlGrid(
            direction=direction,
            required_ratio=required_ratio,
            member_width=member_width,
            effective_depth=effective_depth,
            spacing_limit=spacing_limit,
            bar_size=int(bar_size),
            legs=legs,
            steel_area_per_spacing=steel_area,
            selected_spacing=float(selected_spacing),
            provided_ratio=float(provided_ratio),
            status="OK" if provided_ratio >= required_ratio else "NG",
        )
        for direction in ("vertical", "horizontal")
    )


def check_provided_crack_control_grid(
    member_width, effective_depth, provided, *, required_ratio=0.003,
    absolute_spacing_limit=12.0,
):
    """Check user-provided crack-control reinforcement in both directions.

    The preferred physical input is ``bar_size``, ``legs``, and ``spacing``;
    steel area is derived from the standard bar table. The legacy
    ``steel_area_per_spacing`` form remains accepted for force-only benchmark
    comparisons, but it does not provide a diameter for cage-spacing checks.
    When both forms are supplied, their areas must agree.
    """
    member_width = float(member_width)
    effective_depth = float(effective_depth)
    required_ratio = float(required_ratio)
    absolute_spacing_limit = float(absolute_spacing_limit)
    if any(not np.isfinite(value) or value <= 0.0 for value in (
        member_width, effective_depth, required_ratio, absolute_spacing_limit,
    )):
        raise ValueError("Crack-control dimensions, ratio, and spacing must be positive")
    if set(provided) != {"vertical", "horizontal"}:
        raise ValueError("Provided crack control requires vertical and horizontal entries")
    spacing_limit = min(effective_depth / 4.0, absolute_spacing_limit)
    results = []
    for direction in ("vertical", "horizontal"):
        values = provided[direction]
        spacing = float(values["spacing"])
        bar_size = values.get("bar_size")
        legs = values.get("legs")
        supplied_area = values.get("steel_area_per_spacing")
        if not np.isfinite(spacing) or spacing <= 0.0:
            raise ValueError("Provided crack-control spacing must be positive")
        if (bar_size is None) != (legs is None):
            raise ValueError("Provided crack-control bar_size and legs must be supplied together")
        if bar_size is not None:
            bar_size = int(bar_size)
            legs = int(legs)
            if bar_size not in REBAR_TABLE or legs <= 0:
                raise ValueError("Unknown crack-control bar size or invalid leg count")
            steel_area = legs * REBAR_TABLE[bar_size]["Ab"]
            if supplied_area is not None and not np.isclose(
                steel_area, float(supplied_area), atol=1e-9, rtol=0.0,
            ):
                raise ValueError(
                    "Provided crack-control bar size and legs do not match steel area"
                )
        elif supplied_area is not None:
            steel_area = float(supplied_area)
        else:
            raise ValueError(
                "Provided crack control requires bar_size, legs, and spacing"
            )
        if not np.isfinite(steel_area) or steel_area <= 0.0:
            raise ValueError("Provided crack-control area must be positive")
        provided_ratio = steel_area / (member_width * spacing)
        results.append(CrackControlGrid(
            direction=direction, required_ratio=required_ratio,
            member_width=member_width, effective_depth=effective_depth,
            spacing_limit=spacing_limit, bar_size=bar_size, legs=legs,
            steel_area_per_spacing=steel_area, selected_spacing=spacing,
            provided_ratio=provided_ratio,
            status=(
                "OK" if provided_ratio + 1e-12 >= required_ratio
                and spacing <= spacing_limit + 1e-12 else "NG"
            ),
        ))
    return tuple(results)


def check_provided_tie_bar_layout(
    as_required, section_width, *, bar_count, bar_size, layers=1,
    tie_zone_depth=6.0, clear_cover=2.0, enclosure_bar_size=5,
    minimum_clear_spacing=1.5, maximum_transverse_spacing=12.0,
    maximum_aggregate_size=None, minimum_layer_clear_spacing=1.0,
):
    """Check a compact user-provided longitudinal tie arrangement."""
    as_required = float(as_required)
    section_width = float(section_width)
    tie_zone_depth = float(tie_zone_depth)
    clear_cover = float(clear_cover)
    bar_count, bar_size, layers = int(bar_count), int(bar_size), int(layers)
    if bar_size not in REBAR_TABLE or enclosure_bar_size not in REBAR_TABLE:
        raise ValueError("Unknown longitudinal or enclosure bar size")
    if bar_count < 2 or layers < 1 or layers > bar_count:
        raise ValueError("Provided tie requires at least two bars and valid layers")
    bar = REBAR_TABLE[bar_size]
    enclosure = REBAR_TABLE[enclosure_bar_size]
    base, remainder = divmod(bar_count, layers)
    counts = tuple(base + (index < remainder) for index in range(layers))
    required_clear = max(
        float(minimum_clear_spacing), 1.5 * bar["db"],
        0.0 if maximum_aggregate_size is None
        else 2.0 * float(maximum_aggregate_size),
    )
    center_width = section_width - 2.0 * (
        clear_cover + enclosure["db"] + 0.5 * bar["db"]
    )
    maximum_count = max(counts)
    minimum_count = min(counts)
    transverse_clear = (
        float("inf") if maximum_count == 1
        else center_width / (maximum_count - 1) - bar["db"]
    )
    transverse_center = (
        float("inf") if minimum_count == 1
        else center_width / (minimum_count - 1)
    )
    layer_clear = (
        None if layers == 1
        else (tie_zone_depth - layers * bar["db"]) / (layers - 1)
    )
    as_provided = bar_count * bar["Ab"]
    fits = (
        center_width >= 0.0
        and transverse_clear + 1e-12 >= required_clear
        and transverse_center <= maximum_transverse_spacing + 1e-12
        and (layer_clear is None or layer_clear + 1e-12 >= minimum_layer_clear_spacing)
    )
    return TieBarLayout(
        as_required=as_required, as_provided=as_provided, bar_size=bar_size,
        bar_count=bar_count, layers=layers, bars_per_layer=counts,
        section_width=section_width, tie_zone_depth=tie_zone_depth,
        clear_cover=clear_cover, enclosure_bar_size=int(enclosure_bar_size),
        minimum_clear_spacing=float(minimum_clear_spacing),
        maximum_aggregate_size=maximum_aggregate_size,
        required_transverse_clear_spacing=required_clear,
        minimum_layer_clear_spacing=float(minimum_layer_clear_spacing),
        maximum_transverse_spacing=float(maximum_transverse_spacing),
        transverse_center_spacing=float(transverse_center),
        transverse_clear_spacing=float(transverse_clear),
        layer_clear_spacing=layer_clear,
        status="OK" if as_provided + 1e-12 >= as_required and fits else "NG",
    )


def design_tie_bar_layout(
    as_required, section_width, *, tie_zone_depth=6.0, clear_cover=2.0,
    enclosure_bar_size=5, minimum_clear_spacing=1.5, minimum_bars=2,
    maximum_transverse_spacing=12.0, maximum_layers=2,
    maximum_aggregate_size=None, minimum_layer_clear_spacing=1.0,
    allowed_bar_sizes=(5, 6, 7, 8, 9, 10, 11),
):
    """Select the least-area standard tie layout that fits a rectangular cap.

    Defaults are intentionally visible in the returned record. They provide a
    useful minimum schedule without requiring manual bar inputs, but final
    detailing must still check cover class, laps, and anchorage. When maximum
    aggregate size is supplied, in-layer clear spacing also enforces twice
    that size in accordance with AREMA 2.5.
    """
    as_required = float(as_required)
    section_width = float(section_width)
    tie_zone_depth = float(tie_zone_depth)
    clear_cover = float(clear_cover)
    minimum_clear_spacing = float(minimum_clear_spacing)
    maximum_transverse_spacing = float(maximum_transverse_spacing)
    minimum_layer_clear_spacing = float(minimum_layer_clear_spacing)
    maximum_aggregate_size = (
        None if maximum_aggregate_size is None else float(maximum_aggregate_size)
    )
    minimum_bars = int(minimum_bars)
    maximum_layers = int(maximum_layers)
    values = (
        as_required, section_width, tie_zone_depth, clear_cover,
        minimum_clear_spacing, maximum_transverse_spacing,
        minimum_layer_clear_spacing,
    )
    if any(not np.isfinite(value) for value in values) or as_required <= 0.0:
        raise ValueError("Tie area and detailing dimensions must be positive and finite")
    if min(section_width, tie_zone_depth, clear_cover, minimum_clear_spacing) <= 0.0:
        raise ValueError("Tie detailing dimensions must be positive")
    if maximum_aggregate_size is not None and (
        not np.isfinite(maximum_aggregate_size) or maximum_aggregate_size <= 0.0
    ):
        raise ValueError("maximum_aggregate_size must be positive and finite")
    if minimum_bars < 2 or maximum_layers < 1:
        raise ValueError("Require at least two bars and one permitted layer")
    if enclosure_bar_size not in REBAR_TABLE:
        raise ValueError(f"Unknown enclosure bar size: #{enclosure_bar_size}")
    sizes = tuple(int(size) for size in allowed_bar_sizes)
    if not sizes or any(size not in REBAR_TABLE for size in sizes):
        raise ValueError("allowed_bar_sizes contains an unknown reinforcing bar")

    enclosure_diameter = REBAR_TABLE[enclosure_bar_size]["db"]
    candidates = []
    for size in sizes:
        bar = REBAR_TABLE[size]
        required_transverse_clear = max(
            minimum_clear_spacing,
            1.5 * bar["db"],
            0.0 if maximum_aggregate_size is None else 2.0 * maximum_aggregate_size,
        )
        required_count = max(minimum_bars, int(np.ceil(as_required / bar["Ab"])))
        for count in range(required_count, required_count + 50):
            for layers in range(1, maximum_layers + 1):
                base, remainder = divmod(count, layers)
                counts = tuple(
                    base + (1 if layer < remainder else 0)
                    for layer in range(layers)
                )
                if min(counts) <= 0:
                    continue
                max_count = max(counts)
                center_width = section_width - 2.0 * (
                    clear_cover + enclosure_diameter + 0.5 * bar["db"]
                )
                if center_width < 0.0:
                    continue
                transverse_clear = (
                    float("inf") if max_count == 1
                    else center_width / (max_count - 1) - bar["db"]
                )
                min_count = min(counts)
                transverse_center = (
                    float("inf") if min_count == 1
                    else center_width / (min_count - 1)
                )
                if layers == 1:
                    layer_clear = None
                else:
                    layer_clear = (
                        tie_zone_depth - layers * bar["db"]
                    ) / (layers - 1)
                if transverse_clear + 1e-12 < required_transverse_clear:
                    continue
                if transverse_center - 1e-12 > maximum_transverse_spacing:
                    continue
                if (layer_clear is not None and
                        layer_clear + 1e-12 < minimum_layer_clear_spacing):
                    continue
                provided = count * bar["Ab"]
                candidates.append((
                    provided, layers, count, size, counts,
                    transverse_center, transverse_clear, layer_clear,
                    required_transverse_clear,
                ))
    if not candidates:
        raise ValueError(
            "No permitted tie-bar arrangement fits; revise bar sizes, layers, "
            "tie-zone depth, cover, or section width"
        )
    (provided, layers, count, size, counts, transverse_center,
     transverse_clear, layer_clear, required_transverse_clear) = min(
        candidates, key=lambda item: (item[0], item[1], item[2], item[3])
    )
    return TieBarLayout(
        as_required=as_required,
        as_provided=float(provided),
        bar_size=size,
        bar_count=count,
        layers=layers,
        bars_per_layer=counts,
        section_width=section_width,
        tie_zone_depth=tie_zone_depth,
        clear_cover=clear_cover,
        enclosure_bar_size=int(enclosure_bar_size),
        minimum_clear_spacing=minimum_clear_spacing,
        maximum_aggregate_size=maximum_aggregate_size,
        required_transverse_clear_spacing=float(required_transverse_clear),
        minimum_layer_clear_spacing=minimum_layer_clear_spacing,
        maximum_transverse_spacing=maximum_transverse_spacing,
        transverse_center_spacing=float(transverse_center),
        transverse_clear_spacing=float(transverse_clear),
        layer_clear_spacing=(
            None if layer_clear is None else float(layer_clear)
        ),
        status="OK" if provided >= as_required else "NG",
    )


def calculate_tie_end_anchorage_geometry(
    layer, node_coordinates, member_start, member_end, bar_size, *,
    clear_cover=2.0, enclosure_bar_size=5,
    required_development_lengths=None, anchorage_type="straight",
    critical_section_coordinates=None, critical_section_basis=None,
):
    """Calculate available anchorage at both ends of a continuous tie layer.

    By default, the critical section is the midpoint boundary between the end
    nodal tributary and its adjacent interior nodal tributary. Explicit
    left/right coordinates may replace that proxy when an extended-strut
    boundary has been constructed.
    """
    coordinates = sorted({float(value) for value in node_coordinates})
    if len(coordinates) < 2:
        raise ValueError("At least two tie-node coordinates are required")
    if any(not np.isfinite(value) for value in coordinates):
        raise ValueError("Tie-node coordinates must be finite")
    member_start = float(member_start)
    member_end = float(member_end)
    clear_cover = float(clear_cover)
    if not member_start < coordinates[0] < coordinates[-1] < member_end:
        raise ValueError("Tie nodes must lie strictly inside the member ends")
    if bar_size not in REBAR_TABLE or enclosure_bar_size not in REBAR_TABLE:
        raise ValueError("Unknown tie or enclosure bar size")
    if clear_cover <= 0.0 or not np.isfinite(clear_cover):
        raise ValueError("clear_cover must be positive and finite")
    bar_radius = 0.5 * REBAR_TABLE[bar_size]["db"]
    enclosure_diameter = REBAR_TABLE[enclosure_bar_size]["db"]
    end_offset = clear_cover + enclosure_diameter + bar_radius
    required = {} if required_development_lengths is None else dict(
        required_development_lengths
    )
    unknown_ends = set(required) - {"left", "right"}
    if unknown_ends:
        raise ValueError("Development lengths may be supplied only for left/right ends")
    if isinstance(anchorage_type, dict):
        anchorage_types = dict(anchorage_type)
        if set(anchorage_types) - {"left", "right"}:
            raise ValueError("Anchorage types may be supplied only for left/right ends")
    else:
        anchorage_types = {"left": str(anchorage_type), "right": str(anchorage_type)}
    critical_overrides = (
        {} if critical_section_coordinates is None
        else {key: float(value) for key, value in critical_section_coordinates.items()}
    )
    if set(critical_overrides) - {"left", "right"}:
        raise ValueError("Critical sections may be supplied only for left/right ends")
    if any(not np.isfinite(value) for value in critical_overrides.values()):
        raise ValueError("Critical-section coordinates must be finite")
    basis_overrides = (
        {} if critical_section_basis is None else dict(critical_section_basis)
    )

    definitions = (
        (
            "left", coordinates[0], coordinates[1],
            0.5 * (coordinates[0] + coordinates[1]), member_start + end_offset,
        ),
        (
            "right", coordinates[-1], coordinates[-2],
            0.5 * (coordinates[-1] + coordinates[-2]), member_end - end_offset,
        ),
    )
    geometries = []
    for end, end_node, adjacent, critical, bar_end in definitions:
        critical = critical_overrides.get(end, critical)
        available = (
            critical - bar_end if end == "left" else bar_end - critical
        )
        if available <= 0.0:
            raise ValueError("Calculated anchorage length is not positive")
        required_length = required.get(end)
        if required_length is None:
            status = "REVIEW"
        else:
            required_length = float(required_length)
            if not np.isfinite(required_length) or required_length <= 0.0:
                raise ValueError("Required development lengths must be positive")
            status = "OK" if available >= required_length else "NG"
        geometries.append(TieAnchorageGeometry(
            layer=str(layer), end=end,
            end_node_coordinate=end_node,
            adjacent_node_coordinate=adjacent,
            critical_section_coordinate=critical,
            bar_end_coordinate=bar_end,
            available_length=float(available),
            required_development_length=required_length,
            anchorage_type=anchorage_types.get(end, "straight"),
            status=status,
            basis=(
                basis_overrides.get(
                    end,
                    "available length from preliminary midpoint nodal-tributary "
                    "boundary to bar end",
                ) + (
                    "; required length awaits governing development provisions"
                    if required_length is None else "; required development checked"
                )
            ),
        ))
    return tuple(geometries)


def extended_strut_tie_critical_section(group_geometry, tie_coordinate, end):
    """Intersect an extended prismatic strut boundary with a horizontal tie."""
    if end not in {"left", "right"}:
        raise ValueError("end must be 'left' or 'right'")
    tie_coordinate = float(tie_coordinate)
    axis_start = np.asarray(group_geometry.revised_axis.start, dtype=float)
    axis_end = np.asarray(group_geometry.revised_axis.end, dtype=float)
    direction = axis_end - axis_start
    if not np.isfinite(tie_coordinate) or not np.all(np.isfinite(direction)):
        raise ValueError("Strut and tie coordinates must be finite")
    if abs(direction[1]) <= 1e-12:
        raise ValueError("A horizontal strut boundary cannot intersect a horizontal tie")
    intersections = []
    for point in group_geometry.strut_interface:
        point = np.asarray(point, dtype=float)
        parameter = (tie_coordinate - point[1]) / direction[1]
        intersections.append(float(point[0] + parameter * direction[0]))
    return max(intersections) if end == "left" else min(intersections)


def check_reinforcement_cage_congestion(
    layer, layout, *, member_depth, crack_control_bar_size,
    crack_control_spacing, maximum_aggregate_size,
    hook_projections=(), anchorage_statuses=(),
):
    """Perform an auditable section-level spacing and hook-fit cage screen."""
    member_depth = float(member_depth)
    crack_control_spacing = float(crack_control_spacing)
    maximum_aggregate_size = float(maximum_aggregate_size)
    if crack_control_bar_size not in REBAR_TABLE:
        raise ValueError("Unknown crack-control bar size")
    if any(not np.isfinite(value) or value <= 0.0 for value in (
        member_depth, crack_control_spacing, maximum_aggregate_size,
    )):
        raise ValueError("Cage dimensions and aggregate size must be positive and finite")
    grid_db = REBAR_TABLE[crack_control_bar_size]["db"]
    required_grid_clear = max(1.5, 1.5 * grid_db, 2.0 * maximum_aggregate_size)
    provided_grid_clear = crack_control_spacing - grid_db
    tie_db = REBAR_TABLE[layout.bar_size]["db"]
    enclosure_db = REBAR_TABLE[layout.enclosure_bar_size]["db"]
    available_hook_depth = member_depth - 2.0 * (
        layout.clear_cover + enclosure_db + 0.5 * tie_db
    )
    projections = tuple(float(value) for value in hook_projections)
    maximum_hook = max(projections) if projections else None
    anchorage_status = (
        "OK" if anchorage_statuses and all(value == "OK" for value in anchorage_statuses)
        else "REVIEW" if not anchorage_statuses else "NG"
    )
    checks = [
        layout.transverse_clear_spacing + 1e-12
        >= layout.required_transverse_clear_spacing,
        provided_grid_clear + 1e-12 >= required_grid_clear,
        anchorage_status == "OK",
    ]
    if layout.layer_clear_spacing is not None:
        checks.append(
            layout.layer_clear_spacing + 1e-12
            >= layout.minimum_layer_clear_spacing
        )
    if maximum_hook is not None:
        checks.append(maximum_hook <= available_hook_depth + 1e-12)
    return ReinforcementCageReview(
        layer=str(layer),
        required_transverse_clear_spacing=layout.required_transverse_clear_spacing,
        provided_transverse_clear_spacing=layout.transverse_clear_spacing,
        required_layer_clear_spacing=layout.minimum_layer_clear_spacing,
        provided_layer_clear_spacing=layout.layer_clear_spacing,
        required_crack_control_clear_spacing=float(required_grid_clear),
        provided_crack_control_clear_spacing=float(provided_grid_clear),
        available_hook_depth=float(available_hook_depth),
        maximum_hook_projection=maximum_hook,
        anchorage_status=anchorage_status,
        status="OK" if all(checks) else "NG",
        basis=(
            "AREMA 2.5 aggregate-dependent spacing plus section-level hook-fit "
            "and anchorage screen; final three-dimensional bar-placement drawing "
            "review remains required"
        ),
    )


def calculate_tension_development_length(
    bar_size, fy, fc_prime, *, top_bar=False, lightweight=False,
    epoxy_coated=False, cover=None, clear_spacing=None,
    transverse_reinforcement_area=0.0, transverse_spacing=None,
    bars_in_splitting_plane=1, as_required=None, as_provided=None,
    apply_excess_reinforcement_factor=False,
):
    """Calculate straight-bar tension development per AREMA Section 2.14.

    Stress inputs are ksi and dimensions are inches. ``cover`` is measured
    from the bar center to the nearest concrete surface, as required for
    ``c_b``; ``clear_spacing`` is converted to center spacing internally.
    The optional excess-reinforcement reduction is disabled by default so an
    STM tie required to transfer its force is not credited automatically.
    """
    if bar_size not in REBAR_TABLE:
        raise ValueError(f"Unknown reinforcing bar size: #{bar_size}")
    fy = float(fy)
    fc_prime = float(fc_prime)
    if any(not np.isfinite(value) or value <= 0.0 for value in (fy, fc_prime)):
        raise ValueError("fy and fc_prime must be positive and finite")
    db = float(REBAR_TABLE[bar_size]["db"])

    # AREMA Eq. 2-8.1 is expressed in psi; this is its equivalent for ksi.
    basic = 0.0759 * db * (1000.0 * fy) / np.sqrt(1000.0 * fc_prime)
    top_factor = 1.4 if top_bar else 1.0
    lightweight_factor = 1.3 if lightweight else 1.0

    if cover is None or clear_spacing is None:
        confinement_factor = 1.0
    else:
        cover = float(cover)
        clear_spacing = float(clear_spacing)
        if any(not np.isfinite(value) or value <= 0.0 for value in (
            cover, clear_spacing,
        )):
            raise ValueError("cover and clear_spacing must be positive and finite")
        cb = min(cover, 0.5 * (clear_spacing + db))
        atr = float(transverse_reinforcement_area)
        n = int(bars_in_splitting_plane)
        if not np.isfinite(atr) or atr < 0.0 or n < 1:
            raise ValueError("Transverse reinforcement inputs are invalid")
        if atr == 0.0:
            ktr = 0.0
        else:
            if transverse_spacing is None:
                raise ValueError(
                    "transverse_spacing is required when transverse steel is credited"
                )
            spacing = float(transverse_spacing)
            if not np.isfinite(spacing) or spacing <= 0.0:
                raise ValueError("transverse_spacing must be positive and finite")
            ktr = 40.0 * atr / (spacing * n)
        confinement_factor = min(1.0, max(0.4, db / (cb + ktr)))

    if apply_excess_reinforcement_factor:
        if as_required is None or as_provided is None:
            raise ValueError(
                "as_required and as_provided are required for the excess-steel factor"
            )
        as_required = float(as_required)
        as_provided = float(as_provided)
        if (
            not np.isfinite(as_required) or not np.isfinite(as_provided)
            or as_required <= 0.0 or as_provided < as_required
        ):
            raise ValueError("Reinforcement areas must satisfy 0 < required <= provided")
        excess_factor = as_required / as_provided
    else:
        excess_factor = 1.0

    if epoxy_coated:
        if cover is None or clear_spacing is None:
            raise ValueError("Epoxy factor selection requires cover and clear spacing")
        epoxy_factor = 1.5 if cover < 3.0 * db or clear_spacing < 6.0 * db else 1.2
    else:
        epoxy_factor = 1.0
    combined_top_epoxy = min(top_factor * epoxy_factor, 1.7)
    calculated = (
        basic * combined_top_epoxy * lightweight_factor
        * confinement_factor * excess_factor
    )
    minimum = 12.0
    required = max(calculated, minimum)
    return TensionDevelopmentLength(
        bar_size=int(bar_size), bar_diameter=db, fy=fy, fc_prime=fc_prime,
        basic_length=float(basic), top_bar_factor=top_factor,
        lightweight_factor=lightweight_factor,
        confinement_factor=float(confinement_factor),
        excess_reinforcement_factor=float(excess_factor),
        epoxy_factor=epoxy_factor,
        combined_top_epoxy_factor=float(combined_top_epoxy),
        calculated_length=float(calculated), minimum_length=minimum,
        required_length=float(required),
        basis="AREMA 2025 Section 2.14 and Eq. 2-8.1; US customary units",
    )


def calculate_standard_hook_development(
    bar_size, fy, fc_prime, *, hook_angle=90, epoxy_coated=False,
    adequate_cover=False, adequately_confined=False, lightweight=False,
    as_required=None, as_provided=None,
    apply_excess_reinforcement_factor=False,
):
    """Calculate standard-hook tension development per AREMA 2.17 and 2.4.

    ``adequate_cover`` and ``adequately_confined`` are explicit reviewed
    detailing decisions corresponding to Sections 2.17c(2) and 2.17c(3).
    The returned transverse projection is measured from the straight-bar
    centerline to the far surface of the hook tail for a geometric fit check.
    """
    if bar_size not in REBAR_TABLE or bar_size > 11:
        raise ValueError("Standard-hook development is limited to known bars #11 and smaller")
    hook_angle = int(hook_angle)
    if hook_angle not in (90, 180):
        raise ValueError("Longitudinal-bar standard hooks must be 90 or 180 degrees")
    fy = float(fy)
    fc_prime = float(fc_prime)
    if any(not np.isfinite(value) or value <= 0.0 for value in (fy, fc_prime)):
        raise ValueError("fy and fc_prime must be positive and finite")
    db = float(REBAR_TABLE[bar_size]["db"])
    bend_multiplier = 6.0 if bar_size <= 8 else 8.0
    inside_bend = bend_multiplier * db
    tail = 12.0 * db if hook_angle == 90 else max(4.0 * db, 2.5)
    centerline_radius = 0.5 * (inside_bend + db)
    transverse_projection = (
        centerline_radius + tail + 0.5 * db
        if hook_angle == 90 else inside_bend + 2.0 * db
    )

    basic = 0.02 * db * (1000.0 * fy) / np.sqrt(1000.0 * fc_prime)
    epoxy_factor = 1.2 if epoxy_coated else 1.0
    cover_factor = 0.8 if adequate_cover else 1.0
    confinement_factor = 0.8 if adequately_confined else 1.0
    lightweight_factor = 1.3 if lightweight else 1.0
    if apply_excess_reinforcement_factor:
        if as_required is None or as_provided is None:
            raise ValueError("Reinforcement areas are required for the excess-steel factor")
        as_required = float(as_required)
        as_provided = float(as_provided)
        if (
            not np.isfinite(as_required) or not np.isfinite(as_provided)
            or as_required <= 0.0 or as_provided < as_required
        ):
            raise ValueError("Reinforcement areas must satisfy 0 < required <= provided")
        excess_factor = as_required / as_provided
    else:
        excess_factor = 1.0
    calculated = (
        basic * epoxy_factor * cover_factor * confinement_factor
        * excess_factor * lightweight_factor
    )
    minimum = max(8.0 * db, 6.0)
    return StandardHookDevelopment(
        bar_size=int(bar_size), hook_angle=hook_angle, bar_diameter=db,
        inside_bend_diameter=float(inside_bend), tail_extension=float(tail),
        transverse_projection=float(transverse_projection),
        basic_length=float(basic), epoxy_factor=epoxy_factor,
        cover_factor=cover_factor, confinement_factor=confinement_factor,
        excess_reinforcement_factor=float(excess_factor),
        lightweight_factor=lightweight_factor,
        calculated_length=float(calculated), minimum_length=float(minimum),
        required_length=float(max(calculated, minimum)),
        basis="AREMA 2025 Sections 2.17 and 2.4.1-2.4.2; US customary units",
    )


def calculate_tension_lap_splice(
    bar_size, development_length, *, provided_area_ratio=1.0,
    fraction_spliced=1.0, tension_tie_member=False,
):
    """Calculate a Class A/B tension lap splice per AREMA Section 2.22.3.

    A lap is flagged as prohibited for a tension tie member by Article 2.22.3e;
    the numerical length is still returned for transparent reporting.
    """
    if bar_size not in REBAR_TABLE or bar_size > 11:
        raise ValueError("Tension lap splices are limited to bars #11 and smaller")
    development_length = float(development_length)
    provided_area_ratio = float(provided_area_ratio)
    fraction_spliced = float(fraction_spliced)
    if not np.isfinite(development_length) or development_length <= 0.0:
        raise ValueError("development_length must be positive and finite")
    if not np.isfinite(provided_area_ratio) or provided_area_ratio <= 0.0:
        raise ValueError("provided_area_ratio must be positive and finite")
    if not np.isfinite(fraction_spliced) or not 0.0 < fraction_spliced <= 1.0:
        raise ValueError("fraction_spliced must be between zero and one")
    class_a = provided_area_ratio >= 2.0 and fraction_spliced <= 0.5
    splice_class = "A" if class_a else "B"
    multiplier = 1.0 if class_a else 1.3
    calculated = multiplier * development_length
    minimum = 12.0
    return TensionLapSplice(
        bar_size=int(bar_size), development_length=development_length,
        splice_class=splice_class, multiplier=multiplier,
        calculated_length=float(calculated), minimum_length=minimum,
        required_length=float(max(calculated, minimum)),
        permitted_for_tension_tie_member=not tension_tie_member,
        basis=(
            "AREMA 2025 Section 2.22.3; Article 2.22.3e prohibits lap "
            "splices in tension tie members"
        ),
    )


def construct_single_strut_external_nodal_zone(
    face, truss_model, member_forces, back_face_depth, *, label=None,
    force_tolerance=1e-9,
):
    """Construct a reviewed-plan result when exactly one strut enters a face.

    Any node with zero or multiple compression members is rejected and must use
    an explicit :class:`ExternalNodalZonePlan`.
    """
    nodal_node_id = (
        face.node_id if getattr(face, "nodal_node_id", None) is None
        else face.nodal_node_id
    )
    face_direction = np.asarray(face.end, dtype=float) - np.asarray(face.start, dtype=float)
    face_direction /= np.linalg.norm(face_direction)
    compression_members = []
    for member_id, (ni, nj) in enumerate(truss_model.members):
        if ni != nodal_node_id and nj != nodal_node_id:
            continue
        other = nj if ni == nodal_node_id else ni
        if nodal_node_id != face.node_id and other == face.node_id:
            continue
        if member_forces[member_id] < -force_tolerance:
            direction = np.asarray(truss_model.nodes[other], dtype=float) - np.asarray(
                truss_model.nodes[nodal_node_id], dtype=float
            )
            direction /= np.linalg.norm(direction)
            if abs(float(np.dot(direction, face_direction))) >= 1.0 - 1e-8:
                continue
            compression_members.append((member_id, other))
    if len(compression_members) != 1:
        raise ValueError(
            "Single-strut external-node construction requires exactly one "
            "compression member; supply an explicit reviewed plan"
        )
    member_id, other = compression_members[0]
    group_label = label or f"{face.kind}_{face.source_index}"
    remote_point = np.asarray(truss_model.nodes[other], dtype=float)
    if nodal_node_id != face.node_id:
        remote_point = remote_point + (
            np.asarray(face.center, dtype=float)
            - np.asarray(truss_model.nodes[nodal_node_id], dtype=float)
        )
    plan = ExternalNodalZonePlan(
        node_id=nodal_node_id,
        back_face_depth=back_face_depth,
        groups=(NodalZoneGroupDefinition(
            group_label,
            (member_id,),
            tuple(remote_point),
            classify_nodal_zone(nodal_node_id, truss_model, member_forces),
        ),),
    )
    return construct_subdivided_external_nodal_zone(
        face, truss_model, member_forces, plan
    )[0]


def construct_memberwise_external_nodal_zones(
    face, truss_model, member_forces, back_face_depth, *, label=None,
    force_tolerance=1e-9,
):
    """Propose one force-proportioned tributary for each external strut.

    Compression members are ordered geometrically from ``face.start`` to
    ``face.end``. Each member remains an individual design strut, and the
    finite external face is divided in proportion to the members' force
    components normal to that face. Callers must explicitly opt in because the
    resulting subdivision is a proposed local nodal model requiring review.
    """
    forces = np.asarray(member_forces, dtype=float)
    if forces.shape != (len(truss_model.members),):
        raise ValueError("member_forces must align with truss_model.members")
    depth = float(back_face_depth)
    if not np.isfinite(depth) or depth <= 0.0:
        raise ValueError("back_face_depth must be a positive finite value")
    if not np.isfinite(force_tolerance) or force_tolerance < 0.0:
        raise ValueError("force_tolerance must be nonnegative and finite")

    nodal_node_id = (
        face.node_id if getattr(face, "nodal_node_id", None) is None
        else face.nodal_node_id
    )
    face_start = np.asarray(face.start, dtype=float)
    face_direction = np.asarray(face.end, dtype=float) - face_start
    face_length = np.linalg.norm(face_direction)
    if face_length <= 1e-10:
        raise ValueError("external face has zero length")
    face_direction /= face_length

    compression_members = []
    for member_id, (ni, nj) in enumerate(truss_model.members):
        if ni != nodal_node_id and nj != nodal_node_id:
            continue
        other = nj if ni == nodal_node_id else ni
        if nodal_node_id != face.node_id and other == face.node_id:
            continue
        if forces[member_id] >= -force_tolerance:
            continue
        remote_point = np.asarray(truss_model.nodes[other], dtype=float)
        direction = remote_point - np.asarray(
            truss_model.nodes[nodal_node_id], dtype=float
        )
        length = np.linalg.norm(direction)
        if length <= 1e-10:
            raise ValueError("A strut connected to the external face has zero length")
        direction /= length
        if abs(float(np.dot(direction, face_direction))) >= 1.0 - 1e-8:
            continue
        if nodal_node_id != face.node_id:
            remote_point = remote_point + (
                np.asarray(face.center, dtype=float)
                - np.asarray(truss_model.nodes[nodal_node_id], dtype=float)
            )
        order_coordinate = float(np.dot(remote_point - face_start, face_direction))
        compression_members.append((order_coordinate, member_id, remote_point))

    if not compression_members:
        raise ValueError(
            "External-node construction requires at least one compression member"
        )
    compression_members.sort(key=lambda item: (item[0], item[1]))
    group_prefix = label or f"{face.kind}_{face.source_index}"
    zone_type = classify_nodal_zone(nodal_node_id, truss_model, forces)
    plan = ExternalNodalZonePlan(
        node_id=int(nodal_node_id),
        back_face_depth=depth,
        groups=tuple(
            NodalZoneGroupDefinition(
                f"{group_prefix} / strut {member_id}",
                (int(member_id),), tuple(remote_point), zone_type,
            )
            for _, member_id, remote_point in compression_members
        ),
    )
    return construct_subdivided_external_nodal_zone(
        face, truss_model, forces, plan
    )


def construct_continuous_tie_nodal_zone(
    truss_model, member_forces, node_id, back_face_depth, *,
    assume_continuous_reinforcement=False, split_opposite_sides=False,
    tie_axis=None, tie_boundary_points=(),
    force_tolerance=1e-9, angle_tolerance=1e-8,
):
    """Construct interior CCT geometry for a continuous straight tie node.

    The effective tie face extends to the midpoints of the adjacent tension
    panels. All compression members must enter from one side of that tie axis;
    more complicated interior nodes require an explicit reviewed geometry.
    """
    forces = np.asarray(member_forces, dtype=float)
    if forces.shape != (len(truss_model.members),):
        raise ValueError("member_forces must align with truss_model.members")
    if not 0 <= node_id < len(truss_model.nodes):
        raise ValueError("node_id lies outside the truss model")
    external_nodal_ids = {
        face.nodal_node_id
        for face in getattr(truss_model, "external_faces", ())
        if getattr(face, "nodal_node_id", None) is not None
    }
    if node_id in external_nodal_ids:
        return ()
    depth = float(back_face_depth)
    if not np.isfinite(depth) or depth <= 0.0:
        raise ValueError("back_face_depth must be a positive finite value")

    node = np.asarray(truss_model.nodes[node_id], dtype=float)
    tension = []
    compression = []
    for member_id, ((ni, nj), force) in enumerate(
        zip(truss_model.members, forces)
    ):
        if node_id not in (ni, nj) or abs(force) <= force_tolerance:
            continue
        other = int(nj if ni == node_id else ni)
        vector = np.asarray(truss_model.nodes[other], dtype=float) - node
        length = float(np.linalg.norm(vector))
        if length <= 1e-10:
            raise ValueError("A member connected to the interior node has zero length")
        item = (member_id, other, vector, length)
        if force > 0.0:
            tension.append(item)
        else:
            compression.append(item)
    if not compression:
        raise ValueError("Interior nodal construction requires a compression strut")
    minimum_ties = 0 if tie_axis is not None else (
        1 if assume_continuous_reinforcement else 2
    )
    if len(tension) < minimum_ties:
        raise ValueError("Continuous-tie construction requires a tension tie axis")

    if tie_axis is None:
        axis = tension[0][2] / tension[0][3]
    else:
        axis = np.asarray(tie_axis, dtype=float)
        if axis.shape != (2,) or not np.all(np.isfinite(axis)):
            raise ValueError("tie_axis must be a finite two-dimensional vector")
        axis_length = float(np.linalg.norm(axis))
        if axis_length <= 1e-10:
            raise ValueError("tie_axis must be nonzero")
        axis /= axis_length
    selected_tie_projections = []
    for _, _, vector, _ in tension:
        normal_component = vector - np.dot(vector, axis) * axis
        if np.linalg.norm(normal_component) > angle_tolerance * np.linalg.norm(vector):
            raise ValueError("Interior tension members must share one collinear tie axis")
        selected_tie_projections.append(float(np.dot(vector, axis)))
    if assume_continuous_reinforcement:
        projections = []
        for point in np.asarray(truss_model.nodes, dtype=float):
            vector = point - node
            if np.linalg.norm(vector) <= force_tolerance:
                continue
            normal_component = vector - np.dot(vector, axis) * axis
            if np.linalg.norm(normal_component) <= angle_tolerance * np.linalg.norm(vector):
                projections.append(float(np.dot(vector, axis)))
        for point in tie_boundary_points:
            vector = np.asarray(point, dtype=float) - node
            normal_component = vector - np.dot(vector, axis) * axis
            if np.linalg.norm(normal_component) > angle_tolerance * max(
                1.0, np.linalg.norm(vector)
            ):
                raise ValueError("tie_boundary_points must lie on the tie axis")
            projections.append(float(np.dot(vector, axis)))
    else:
        projections = selected_tie_projections
    negative = [value for value in projections if value < -force_tolerance]
    positive = [value for value in projections if value > force_tolerance]
    if not negative or not positive:
        raise ValueError("Continuous-tie construction requires a tie panel on each side")

    normal = np.array([-axis[1], axis[0]])
    side_components = [float(np.dot(item[2], normal)) for item in compression]
    transverse = [
        (item, component) for item, component in zip(compression, side_components)
        if abs(component) > force_tolerance
    ]
    parallel = [
        item for item, component in zip(compression, side_components)
        if abs(component) <= force_tolerance
    ]
    transverse_components = [component for _, component in transverse]
    opposite_sides = (
        transverse_components
        and min(transverse_components) < -force_tolerance
        < max(transverse_components)
    )
    if opposite_sides and not split_opposite_sides:
        raise ValueError(
            "Compression struts enter from both sides of the tie; supply an "
            "explicit reviewed interior-node geometry"
        )
    zone_type = classify_nodal_zone(node_id, truss_model, forces)
    if zone_type not in ("CCC", "CCT"):
        raise ValueError("Continuous-tie construction supports CCC and CCT nodes only")

    start_offset = 0.5 * max(negative)
    end_offset = 0.5 * min(positive)
    face_centerline_start = node + start_offset * axis
    face_centerline_end = node + end_offset * axis

    side_groups = []
    for side_sign in (-1.0, 1.0):
        members = [
            item for item, component in transverse
            if component * side_sign > force_tolerance
        ]
        if members:
            side_groups.append((side_sign, members))
    geometries = []
    for side_sign, side_members in side_groups:
        side_normal = side_sign * normal
        # Adjacent continuous nodes share their common panel at its midpoint.
        baseline_shift = -0.5 * depth * side_normal
        face_start = face_centerline_start + baseline_shift
        face_end = face_centerline_end + baseline_shift
        face = ExternalFace(
            kind="interior_tie_face",
            source_index=-1,
            node_id=int(node_id),
            center=tuple(0.5 * (face_start + face_end)),
            start=tuple(face_start),
            end=tuple(face_end),
            width=float(np.linalg.norm(face_end - face_start)),
            inward_normal=tuple(side_normal),
        )
        side_members.sort(key=lambda item: float(np.dot(item[2], axis)))
        side_label = "positive" if side_sign > 0.0 else "negative"
        plan = ExternalNodalZonePlan(
            node_id=int(node_id),
            back_face_depth=depth,
            groups=tuple(
                NodalZoneGroupDefinition(
                    label=f"node_{node_id}_{side_label}_member_{member_id}",
                    member_ids=(int(member_id),),
                    remote_point=tuple(truss_model.nodes[other]),
                    zone_type=zone_type,
                )
                for member_id, other, _, _ in side_members
            ),
        )
        geometries.extend(construct_subdivided_external_nodal_zone(
            face, truss_model, forces, plan
        ))

    # A compression member parallel to the tie terminates on the rectangular
    # node's side face, whose dimension normal to that member is the back depth.
    for member_id, other, vector, _ in parallel:
        direction_sign = 1.0 if np.dot(vector, axis) > 0.0 else -1.0
        side_normal = normal
        baseline_shift = -0.5 * depth * side_normal
        side_centerline = (
            face_centerline_end if direction_sign > 0.0
            else face_centerline_start
        )
        interface = (
            tuple(side_centerline + baseline_shift),
            tuple(side_centerline + baseline_shift + depth * side_normal),
        )
        tributary = NodalFaceTributary(
            node_id=int(node_id), source_index=-1,
            parent_kind="interior_tie_side_face",
            label=f"node_{node_id}_parallel_member_{member_id}",
            center=tuple(side_centerline), start=interface[0], end=interface[1],
            width=depth, normal_force=abs(float(forces[member_id])),
        )
        revised_axis = revise_strut_axis_through_tributary(
            tributary, tuple(truss_model.nodes[other])
        )
        polygon = (
            tuple(face_centerline_start + baseline_shift),
            tuple(face_centerline_end + baseline_shift),
            tuple(face_centerline_end + baseline_shift + depth * side_normal),
            tuple(face_centerline_start + baseline_shift + depth * side_normal),
        )
        geometries.append(NodalZoneGroupGeometry(
            label=tributary.label, zone_type=zone_type,
            member_ids=(int(member_id),),
            resultant=resolve_member_forces_at_node(
                truss_model, forces, node_id, (member_id,)
            ),
            tributary=tributary, revised_axis=revised_axis,
            strut_interface_width=depth, nodal_polygon=polygon,
            strut_interface=interface,
        ))
    return tuple(geometries)


def construct_subdivided_external_nodal_zone(
    face, truss_model, member_forces, plan,
):
    """Execute an engineer-reviewed multi-strut external-node plan."""
    valid_node_ids = {face.node_id}
    if getattr(face, "nodal_node_id", None) is not None:
        valid_node_ids.add(face.nodal_node_id)
    if plan.node_id not in valid_node_ids:
        raise ValueError("External face and nodal-zone plan reference different nodes")
    if not plan.groups:
        raise ValueError("Nodal-zone plan requires at least one member group")
    if plan.back_face_depth <= 0.0 or not np.isfinite(plan.back_face_depth):
        raise ValueError("back_face_depth must be a positive finite value")
    labels = [group.label for group in plan.groups]
    if len(set(labels)) != len(labels) or any(not str(label).strip() for label in labels):
        raise ValueError("Nodal-zone group labels must be nonempty and unique")
    all_members = [member for group in plan.groups for member in group.member_ids]
    if len(set(all_members)) != len(all_members):
        raise ValueError("A member cannot belong to more than one nodal-zone group")
    if any(group.zone_type not in ("CCC", "CCT", "CTT") for group in plan.groups):
        raise ValueError("Each nodal-zone group requires a CCC, CCT, or CTT type")

    face_vector = np.asarray(face.end, dtype=float) - np.asarray(face.start, dtype=float)
    face_direction = face_vector / np.linalg.norm(face_vector)
    face_normal = np.array([-face_direction[1], face_direction[0]])
    resultants = [
        resolve_member_forces_at_node(
            truss_model, member_forces, plan.node_id, group.member_ids
        )
        for group in plan.groups
    ]
    normal_forces = [
        abs(float(np.dot(resultant.vector, face_normal)))
        for resultant in resultants
    ]
    tributaries = subdivide_external_face(face, normal_forces, labels=labels)

    geometries = []
    for group, resultant, tributary in zip(plan.groups, resultants, tributaries):
        axis = revise_strut_axis_through_tributary(tributary, group.remote_point)
        polygon, interface = construct_projected_nodal_envelope(
            tributary, face.inward_normal, plan.back_face_depth, axis
        )
        interface_width = float(np.linalg.norm(
            np.asarray(interface[1]) - np.asarray(interface[0])
        ))
        geometries.append(NodalZoneGroupGeometry(
            label=group.label,
            zone_type=group.zone_type,
            member_ids=tuple(group.member_ids),
            resultant=resultant,
            tributary=tributary,
            revised_axis=axis,
            strut_interface_width=interface_width,
            nodal_polygon=polygon,
            strut_interface=interface,
        ))
    return tuple(geometries)


def check_nodal_face_capacity(
    demand, face_width, b, fc_prime, stress_factor, *, phi=0.75,
    confinement_factor=1.0, node_id=-1, group_label="isolated",
    zone_type="reviewed", face_type="reviewed",
):
    """Check one explicitly defined nodal face.

    This small calculation is shared by constructed nodal zones and published
    benchmarks so geometry, stress factor, resistance factor, and confinement
    remain visible rather than being embedded in a benchmark-only equation.
    """
    demand = float(demand)
    face_width = float(face_width)
    b = float(b)
    fc_prime = float(fc_prime)
    stress_factor = float(stress_factor)
    phi = float(phi)
    confinement_factor = float(confinement_factor)
    if not np.isfinite(demand) or demand < 0.0:
        raise ValueError("Nodal-face demand must be nonnegative and finite")
    if any(not np.isfinite(value) or value <= 0.0 for value in (
        face_width, b, fc_prime, stress_factor, phi, confinement_factor,
    )):
        raise ValueError("Nodal-face dimensions and factors must be positive and finite")
    if confinement_factor > 2.0:
        raise ValueError("confinement_factor must not exceed 2.0")
    area = face_width * b
    fcu = confinement_factor * stress_factor * fc_prime
    capacity = phi * fcu * area
    dc_ratio = demand / capacity
    return NodalFaceCheck(
        node_id=int(node_id), group_label=str(group_label),
        zone_type=str(zone_type), face_type=str(face_type), demand=demand,
        face_width=face_width, area=float(area),
        stress_factor=stress_factor, confinement_factor=confinement_factor,
        fcu=float(fcu), capacity=float(capacity), dc_ratio=float(dc_ratio),
        status="OK" if dc_ratio <= 1.0 else "NG", phi=phi,
    )


def check_subdivided_nodal_zone_faces(
    group_geometry, b, fc_prime, *, phi=0.75, stress_factors=None,
    confinement_factor=1.0,
):
    """Check bearing, back, and strut-interface faces of one nodal group.

    Stress factors remain explicit/configurable because the governing code
    edition and owner criteria have not yet been selected for this project.
    """
    b = float(b)
    fc_prime = float(fc_prime)
    phi = float(phi)
    confinement_factor = float(confinement_factor)
    if not np.isfinite(b) or b <= 0.0:
        raise ValueError("Out-of-plane width b must be positive and finite")
    if not np.isfinite(fc_prime) or fc_prime <= 0.0:
        raise ValueError("fc_prime must be positive and finite")
    if not np.isfinite(phi) or phi <= 0.0:
        raise ValueError("phi must be positive and finite")
    if not np.isfinite(confinement_factor) or not 0.0 < confinement_factor <= 2.0:
        raise ValueError("confinement_factor must be in the interval (0, 2]")

    tributary = group_geometry.tributary
    tangent = np.asarray(tributary.end) - np.asarray(tributary.start)
    tangent /= np.linalg.norm(tangent)
    back_width = float(np.linalg.norm(
        np.asarray(group_geometry.nodal_polygon[3])
        - np.asarray(group_geometry.nodal_polygon[0])
    ))
    back_demand = abs(float(np.dot(group_geometry.resultant.vector, tangent)))
    faces = (
        ("bearing", tributary.normal_force, tributary.width),
        ("back", back_demand, back_width),
        ("strut_interface", group_geometry.resultant.magnitude,
         group_geometry.strut_interface_width),
    )
    checks = []
    for face_type, demand, face_width in faces:
        factor = _nodal_face_stress_factor(
            group_geometry.zone_type, face_type, stress_factors
        )
        checks.append(check_nodal_face_capacity(
            demand, face_width, b, fc_prime, factor, phi=phi,
            confinement_factor=confinement_factor,
            node_id=tributary.node_id, group_label=group_geometry.label,
            zone_type=group_geometry.zone_type, face_type=face_type,
        ))
    return tuple(checks)


def check_interior_nodal_zone_faces(
    group_geometry, b, fc_prime, *, phi=0.75, stress_factors=None,
    confinement_factor=1.0,
):
    """Conservatively check the three faces of a constructed interior node.

    The continuous-tie tributary is treated as a bounded smeared nodal face.
    No confinement enhancement or fan spreading is implied. The same nodal
    stress factor applies to its tie-boundary, opposite boundary, and explicitly
    projected strut interface unless the selected code profile overrides it.
    """
    if not group_geometry.tributary.parent_kind.startswith("interior_tie"):
        raise ValueError("Interior nodal checks require interior-tie geometry")
    checks = check_subdivided_nodal_zone_faces(
        group_geometry, b, fc_prime, phi=phi,
        stress_factors=stress_factors,
        confinement_factor=confinement_factor,
    )
    names = {
        "bearing": "tie_boundary",
        "back": "opposite_boundary",
        "strut_interface": "strut_interface",
    }
    return tuple(replace(check, face_type=names[check.face_type]) for check in checks)


def _nodal_face_stress_factor(zone_type, face_type, stress_factors):
    defaults = {"CCC": 0.85, "CCT": 0.75, "CTT": 0.65}
    if zone_type not in defaults:
        raise ValueError(f"Unknown nodal zone type: {zone_type!r}")
    if stress_factors is None:
        return defaults[zone_type]
    value = stress_factors.get(zone_type, defaults[zone_type])
    if isinstance(value, dict):
        value = value.get(face_type, value.get("default"))
        if value is None:
            raise ValueError(f"No stress factor for {zone_type} {face_type} face")
    value = float(value)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError("Nodal face stress factors must be positive and finite")
    return value


def resolve_member_forces_at_node(
    truss_model, member_forces, node_id, member_ids,
):
    """Resolve selected connected-member actions into one nodal force vector.

    The returned vector is the force exerted by the selected members on the
    node, using the package convention of positive tension and negative
    compression. Member grouping remains an explicit engineering decision.
    """
    selected = tuple(int(member_id) for member_id in member_ids)
    if not selected:
        raise ValueError("member_ids must contain at least one member")
    if len(set(selected)) != len(selected):
        raise ValueError("member_ids must not contain duplicates")
    forces = np.asarray(member_forces, dtype=float)
    if forces.shape != (len(truss_model.members),):
        raise ValueError("member_forces must align with truss_model.members")
    if not 0 <= node_id < len(truss_model.nodes):
        raise ValueError("node_id lies outside the truss model")

    resultant = np.zeros(2)
    for member_id in selected:
        if not 0 <= member_id < len(truss_model.members):
            raise ValueError("member_ids contains an unknown member")
        ni, nj = truss_model.members[member_id]
        if ni == node_id:
            other = nj
        elif nj == node_id:
            other = ni
        else:
            raise ValueError(
                f"Member {member_id} is not connected to node {node_id}"
            )
        delta = truss_model.nodes[other] - truss_model.nodes[node_id]
        length = np.linalg.norm(delta)
        if length <= 1e-10:
            raise ValueError(f"Member {member_id} has zero length")
        resultant += forces[member_id] * delta / length

    magnitude = float(np.linalg.norm(resultant))
    if magnitude <= 1e-10:
        raise ValueError("Selected member forces have a zero resultant")
    angle = float(np.degrees(np.arctan2(abs(resultant[1]), abs(resultant[0]))))
    return ResolvedNodalForce(
        node_id=node_id,
        member_ids=selected,
        vector=tuple(resultant),
        magnitude=magnitude,
        angle_degrees=angle,
    )


def revise_strut_axis_through_tributary(tributary, remote_point):
    """Return the axis from a tributary centroid to the remote truss node."""
    start = np.asarray(tributary.center, dtype=float)
    end = np.asarray(remote_point, dtype=float)
    delta = end - start
    length = float(np.linalg.norm(delta))
    if length <= 1e-10:
        raise ValueError("remote_point must differ from the tributary centroid")
    angle = float(np.degrees(np.arctan2(abs(delta[1]), abs(delta[0]))))
    return RevisedStrutAxis(
        start=tuple(start), end=tuple(end), length=length,
        angle_degrees=angle,
    )


def projected_strut_interface_width(face_width, back_face_depth, angle_degrees):
    """Project finite bearing and back faces normal to a strut axis."""
    lb = float(face_width)
    ha = float(back_face_depth)
    theta = float(angle_degrees)
    if not np.isfinite(lb) or lb <= 0.0:
        raise ValueError("face_width must be a positive finite value")
    if not np.isfinite(ha) or ha <= 0.0:
        raise ValueError("back_face_depth must be a positive finite value")
    if not np.isfinite(theta) or not 0.0 <= theta <= 90.0:
        raise ValueError("angle_degrees must be between 0 and 90")
    radians = np.radians(theta)
    return float(lb * np.sin(radians) + ha * np.cos(radians))


def extended_nodal_zone_anchorage_length(
    bearing_width, back_face_depth, strut_angle_degrees,
    end_overhang, clear_cover,
):
    """Available tie anchorage to an extended prismatic-strut boundary.

    This is the construction used in FHWA-NHI-130126 Figure 1-21: the critical
    section lies where the tie centroid exits the edge of a prismatic strut.
    ``end_overhang`` is measured from the outer bearing edge to the member end.
    """
    lb = float(bearing_width)
    ha = float(back_face_depth)
    theta = float(strut_angle_degrees)
    overhang = float(end_overhang)
    cover = float(clear_cover)
    if any(not np.isfinite(value) or value <= 0.0 for value in (
        lb, ha, theta, overhang, cover,
    )):
        raise ValueError("Anchorage geometry inputs must be positive and finite")
    if theta >= 90.0:
        raise ValueError("strut_angle_degrees must be less than 90")
    horizontal_projection = 0.5 * ha / np.tan(np.radians(theta))
    available = horizontal_projection + lb + overhang - cover
    if available <= 0.0:
        raise ValueError("Calculated anchorage length is not positive")
    return float(available)


def construct_projected_nodal_envelope(
    tributary, inward_normal, back_face_depth, revised_axis,
):
    """Construct a rectangular nodal envelope and its projected strut face."""
    start = np.asarray(tributary.start, dtype=float)
    end = np.asarray(tributary.end, dtype=float)
    tangent = end - start
    tangent_length = np.linalg.norm(tangent)
    if tangent_length <= 1e-10:
        raise ValueError("Nodal face tributary has zero length")
    tangent /= tangent_length
    inward = np.asarray(inward_normal, dtype=float)
    inward_length = np.linalg.norm(inward)
    if inward_length <= 1e-10:
        raise ValueError("inward_normal must be nonzero")
    inward /= inward_length
    if abs(float(np.dot(tangent, inward))) > 1e-8:
        raise ValueError("inward_normal must be perpendicular to the external face")
    depth = float(back_face_depth)
    if not np.isfinite(depth) or depth <= 0.0:
        raise ValueError("back_face_depth must be a positive finite value")

    polygon_array = np.array([
        start,
        end,
        end + depth * inward,
        start + depth * inward,
    ])
    axis_vector = np.asarray(revised_axis.end) - np.asarray(revised_axis.start)
    axis_vector /= np.linalg.norm(axis_vector)
    interface_direction = np.array([-axis_vector[1], axis_vector[0]])
    axis_start = np.asarray(revised_axis.start, dtype=float)
    offsets = (polygon_array - axis_start) @ interface_direction
    interface = (
        tuple(axis_start + np.min(offsets) * interface_direction),
        tuple(axis_start + np.max(offsets) * interface_direction),
    )
    return tuple(map(tuple, polygon_array)), interface


def subdivide_external_face(face, normal_forces, *, labels=None):
    """Split a finite face into uniform-pressure force tributaries.

    Tributaries follow the supplied order from ``face.start`` to ``face.end``.
    Their widths are proportional to positive force components normal to the
    face, so both total face width and total normal force are conserved.
    """
    forces = np.asarray(normal_forces, dtype=float)
    if forces.ndim != 1 or len(forces) == 0:
        raise ValueError("normal_forces must be a nonempty one-dimensional sequence")
    if np.any(~np.isfinite(forces)) or np.any(forces <= 0.0):
        raise ValueError("normal force tributaries must be positive and finite")
    if labels is None:
        labels = [str(index) for index in range(len(forces))]
    if len(labels) != len(forces):
        raise ValueError("labels must align with normal_forces")

    start = np.asarray(face.start, dtype=float)
    end = np.asarray(face.end, dtype=float)
    face_vector = end - start
    geometric_width = np.linalg.norm(face_vector)
    if not np.isclose(geometric_width, face.width, rtol=1e-9, atol=1e-9):
        raise ValueError("external face endpoints do not match its stated width")
    direction = face_vector / geometric_width
    widths = face.width * forces / np.sum(forces)

    tributaries = []
    cursor = start.copy()
    for label, force, width in zip(labels, forces, widths):
        tributary_end = cursor + width * direction
        center = 0.5 * (cursor + tributary_end)
        tributaries.append(NodalFaceTributary(
            node_id=(
                face.node_id if getattr(face, "nodal_node_id", None) is None
                else face.nodal_node_id
            ),
            source_index=face.source_index,
            parent_kind=face.kind,
            label=str(label),
            center=tuple(center),
            start=tuple(cursor),
            end=tuple(tributary_end),
            width=float(width),
            normal_force=float(force),
        ))
        cursor = tributary_end
    return tributaries


def construct_external_nodal_zone(
    face, truss_model, member_forces, back_face_depth, *, force_tolerance=1e-9,
):
    """Construct a singular external node using projected face dimensions.

    This implements the FHWA/AASHTO construction
    ``w = lb*sin(theta) + ha*cos(theta)`` for one compression strut entering a
    finite bearing face. Nodes with multiple compression struts require force
    tributaries and subdivision and are deliberately rejected.
    """
    ha = float(back_face_depth)
    if not np.isfinite(ha) or ha <= 0.0:
        raise ValueError("back_face_depth must be a positive finite value")
    if not np.isfinite(face.width) or face.width <= 0.0:
        raise ValueError("external face width must be a positive finite value")

    compression_members = []
    for member_id, (ni, nj) in enumerate(truss_model.members):
        if ni != face.node_id and nj != face.node_id:
            continue
        if member_forces[member_id] >= -force_tolerance:
            continue
        other = nj if ni == face.node_id else ni
        direction = truss_model.nodes[other] - truss_model.nodes[face.node_id]
        length = np.linalg.norm(direction)
        if length <= 1e-10:
            raise ValueError("A strut connected to the external face has zero length")
        compression_members.append((member_id, direction / length))

    if len(compression_members) != 1:
        raise ValueError(
            "Singular external-node construction requires exactly one "
            "compression strut; subdivide nodes with multiple struts"
        )

    member_id, strut_direction = compression_members[0]
    face_vector = np.asarray(face.end) - np.asarray(face.start)
    face_direction = face_vector / np.linalg.norm(face_vector)
    cosine = abs(float(np.dot(strut_direction, face_direction)))
    cosine = min(1.0, max(0.0, cosine))
    sine = float(np.sqrt(max(0.0, 1.0 - cosine ** 2)))
    theta = float(np.degrees(np.arctan2(sine, cosine)))
    interface_width = projected_strut_interface_width(face.width, ha, theta)

    interface_direction = np.array([-strut_direction[1], strut_direction[0]])
    center = np.asarray(face.center, dtype=float)
    half_interface = 0.5 * interface_width * interface_direction
    interface = (
        tuple(center - half_interface),
        tuple(center + half_interface),
    )
    zone_type = classify_nodal_zone(
        face.node_id, truss_model, member_forces
    )
    return NodalZoneGeometry(
        node_id=face.node_id,
        zone_type=zone_type,
        bearing_face=(tuple(face.start), tuple(face.end)),
        back_face_depth=ha,
        strut_member_id=member_id,
        strut_angle_degrees=theta,
        strut_interface_width=interface_width,
        strut_interface=interface,
    )


def check_strut(
    member_id, force, strut_width, b, fc_prime, eps_1=0.002, *,
    phi=0.75, fcu_cap_factor=0.85,
):
    """
    AASHTO 5.8.2.5.3.1 strut capacity check.

    Parameters
    ----------
    member_id : member index
    force : axial force (kip), negative for compression
    strut_width : effective strut width (in)
    b : out-of-plane thickness (in)
    fc_prime : concrete compressive strength (ksi)
    eps_1 : principal tensile strain (default 0.002 for conservative estimate)

    Returns
    -------
    StrutCheck dataclass
    """
    Pu = abs(force)

    # AASHTO Eq. 5.8.2.5.3.1-1: limiting compressive stress
    fcu = fc_prime / (0.8 + 170.0 * eps_1)
    fcu = min(fcu, fcu_cap_factor * fc_prime)

    # Strut area
    Acs = strut_width * b
    capacity = phi * fcu * Acs

    dc = Pu / capacity if capacity > 0 else float('inf')
    status = 'OK' if dc <= 1.0 else 'NG'

    return StrutCheck(
        member_id=member_id,
        force=force,
        strut_width=strut_width,
        strut_area=Acs,
        fcu=fcu,
        capacity=capacity,
        dc_ratio=dc,
        status=status,
        phi=phi,
    )


def required_reinforced_strut_steel_area(
    demand, concrete_capacity, fy, *, phi=0.70, steel_factor=0.80,
):
    """Steel area required to supplement a deficient concrete strut capacity."""
    demand = float(demand)
    concrete_capacity = float(concrete_capacity)
    fy = float(fy)
    phi = float(phi)
    steel_factor = float(steel_factor)
    if any(not np.isfinite(value) or value <= 0.0 for value in (
        demand, concrete_capacity, fy, phi, steel_factor,
    )):
        raise ValueError("Reinforced-strut inputs must be positive and finite")
    deficiency = max(0.0, demand - concrete_capacity)
    return float(deficiency / (steel_factor * phi * fy))


def check_tie(
    member_id, force, fy=60.0, *, phi=0.90, preferred_bar_size=None,
    min_bars=2,
):
    """
    AASHTO 5.8.2.4.1 tie reinforcement check.

    Parameters
    ----------
    member_id : member index
    force : axial force (kip), positive for tension
    fy : reinforcement yield strength (ksi)

    Returns
    -------
    TieCheck dataclass
    """
    Tu = abs(force)
    As_req = Tu / (phi * fy)

    bar_size, n_bars, As_prov = select_bars(
        As_req, preferred_size=preferred_bar_size, min_bars=min_bars
    )

    dc = As_req / As_prov if As_prov > 0 else float('inf')
    status = 'OK' if dc <= 1.0 else 'NG'

    return TieCheck(
        member_id=member_id,
        force=force,
        As_required=As_req,
        As_provided=As_prov,
        bar_size=bar_size,
        n_bars=n_bars,
        dc_ratio=dc,
        status=status,
        phi=phi,
        fy=fy,
    )


def select_bars(As_required, *, preferred_size=None, min_bars=2):
    """
    Select practical bar size and count to provide >= As_required.

    Parameters
    ----------
    As_required : required steel area (in^2)

    Returns
    -------
    bar_size : rebar number
    n_bars : number of bars
    As_provided : provided area (in^2)
    """
    if min_bars < 1:
        raise ValueError("min_bars must be at least one")
    if preferred_size is not None:
        if preferred_size not in REBAR_TABLE:
            raise ValueError(f"Unknown preferred bar size: #{preferred_size}")
        area = REBAR_TABLE[preferred_size]['Ab']
        count = max(min_bars, int(np.ceil(max(As_required, 0.0) / area)))
        return preferred_size, count, count * area
    if As_required <= 0:
        return 4, min_bars, min_bars * REBAR_TABLE[4]['Ab']

    best = None
    for size in [5, 6, 7, 8, 9, 10, 11]:
        Ab = REBAR_TABLE[size]['Ab']
        n = int(np.ceil(As_required / Ab))
        n = max(n, min_bars)
        As_prov = n * Ab
        # Prefer fewer bars of larger size, but not too few
        if best is None or n < best[1] or (n == best[1] and size < best[0]):
            best = (size, n, As_prov)

    return best


def classify_nodal_zone(node_id, truss_model, member_forces):
    """
    Classify a nodal zone as CCC, CCT, or CTT based on framing members.

    CCC = all compression (or no tension)
    CCT = one or more tension ties
    CTT = two or more tension ties

    Parameters
    ----------
    node_id : truss node index
    truss_model : TrussModel
    member_forces : (n_members,) axial forces

    Returns
    -------
    zone_type : 'CCC', 'CCT', or 'CTT'
    """
    tension_axes = []
    for mid, (ni, nj) in enumerate(truss_model.members):
        if ni == node_id or nj == node_id:
            if member_forces[mid] > 0:  # tension
                other = nj if ni == node_id else ni
                direction = truss_model.nodes[other] - truss_model.nodes[node_id]
                direction = direction / np.linalg.norm(direction)
                # Opposite collinear chord segments represent one continuous
                # tie axis rather than two independent ties.
                if direction[0] < -1e-10 or (
                    abs(direction[0]) <= 1e-10 and direction[1] < 0
                ):
                    direction = -direction
                if not any(abs(np.dot(direction, axis)) >= 1.0 - 1e-8
                           for axis in tension_axes):
                    tension_axes.append(direction)

    if len(tension_axes) == 0:
        return 'CCC'
    elif len(tension_axes) == 1:
        return 'CCT'
    else:
        return 'CTT'


def check_nodal_zone(
    node_id, zone_type, max_force, bearing_width, b, fc_prime, *, phi=0.75,
    stress_factors=None,
):
    """
    AASHTO 5.8.2.5.3.2 nodal zone capacity check.

    Limiting stress factors:
    - CCC: 0.85 * f'c
    - CCT: 0.75 * f'c
    - CTT: 0.65 * f'c

    Parameters
    ----------
    node_id : truss node index
    zone_type : 'CCC', 'CCT', or 'CTT'
    max_force : maximum force at the node (kip)
    bearing_width : bearing plate width or effective width (in)
    b : out-of-plane thickness (in)
    fc_prime : concrete compressive strength (ksi)

    Returns
    -------
    NodalZoneCheck dataclass
    """
    if stress_factors is None:
        stress_factors = {'CCC': 0.85, 'CCT': 0.75, 'CTT': 0.65}
    factor = stress_factors.get(zone_type, 0.65)

    fcu_node = factor * fc_prime
    bearing_area = bearing_width * b
    capacity = phi * fcu_node * bearing_area

    Pu = abs(max_force)
    dc = Pu / capacity if capacity > 0 else float('inf')
    status = 'OK' if dc <= 1.0 else 'NG'

    return NodalZoneCheck(
        node_id=node_id,
        zone_type=zone_type,
        max_force=max_force,
        bearing_area=bearing_area,
        fcu_node=fcu_node,
        capacity=capacity,
        dc_ratio=dc,
        status=status,
        phi=phi,
    )


def minimum_crack_control_reinforcement(b, s, fy=60.0):
    """
    AASHTO 5.8.2.6 minimum crack-control reinforcement.

    Required: Av >= 0.003 * b * s in each orthogonal direction.

    Parameters
    ----------
    b : beam width (in)
    s : bar spacing (in)
    fy : yield strength (ksi)

    Returns
    -------
    Av_min : minimum area per layer (in^2)
    bar_size : recommended bar size
    spacing : recommended spacing (in)
    """
    Av_min = 0.003 * b * s
    bar_size, n_bars, _ = select_bars(Av_min)
    return Av_min, bar_size, s


def run_all_checks(truss_model, member_forces, supports, loads,
                   fc_prime, fy, b, bearing_width=8.0):
    """
    Run comprehensive AASHTO design checks on the truss model.

    Parameters
    ----------
    truss_model : TrussModel
    member_forces : (n_members,) axial forces (kip)
    supports : list of support dicts
    loads : list of load dicts
    fc_prime : concrete compressive strength (ksi)
    fy : steel yield strength (ksi)
    b : out-of-plane thickness (in)
    bearing_width : bearing plate width (in)

    Returns
    -------
    strut_checks : list of StrutCheck
    tie_checks : list of TieCheck
    node_checks : list of NodalZoneCheck
    """
    strut_checks = []
    tie_checks = []

    for mid in range(len(truss_model.members)):
        force = member_forces[mid]
        mtype = truss_model.member_types[mid]

        if mtype == 'strut' or force < 0:
            # Strut check
            width = (truss_model.member_widths[mid]
                     if mid < len(truss_model.member_widths)
                     else 5.0)
            sc = check_strut(mid, force, width, b, fc_prime)
            strut_checks.append(sc)

        if mtype == 'tie' or force > 0:
            # Tie check
            tc = check_tie(mid, force, fy)
            tie_checks.append(tc)

    # Nodal zone checks
    node_checks = []
    checked_nodes = set()

    face_widths = {
        face.node_id: face.width
        for face in getattr(truss_model, 'external_faces', [])
    }

    # Check support nodes
    for si in truss_model.support_node_ids:
        nid = truss_model.support_node_ids[si]
        if nid in checked_nodes:
            continue
        checked_nodes.add(nid)
        zone_type = classify_nodal_zone(nid, truss_model, member_forces)
        max_f = _max_force_at_node(nid, truss_model, member_forces)
        width = face_widths.get(nid, bearing_width)
        nc = check_nodal_zone(nid, zone_type, max_f, width, b, fc_prime)
        node_checks.append(nc)

    # Check load nodes
    for li in truss_model.load_node_ids:
        nid = truss_model.load_node_ids[li]
        if nid in checked_nodes:
            continue
        checked_nodes.add(nid)
        zone_type = classify_nodal_zone(nid, truss_model, member_forces)
        max_f = _max_force_at_node(nid, truss_model, member_forces)
        width = face_widths.get(nid, bearing_width)
        nc = check_nodal_zone(nid, zone_type, max_f, width, b, fc_prime)
        node_checks.append(nc)

    # Check interior nodes (degree >= 3)
    for nid in range(len(truss_model.nodes)):
        if nid in checked_nodes:
            continue
        member_count = sum(1 for ni, nj in truss_model.members if ni == nid or nj == nid)
        if member_count >= 3:
            checked_nodes.add(nid)
            zone_type = classify_nodal_zone(nid, truss_model, member_forces)
            max_f = _max_force_at_node(nid, truss_model, member_forces)
            nc = check_nodal_zone(nid, zone_type, max_f, bearing_width, b, fc_prime)
            node_checks.append(nc)

    return strut_checks, tie_checks, node_checks


def _max_force_at_node(node_id, truss_model, member_forces):
    """Maximum absolute force among members framing into a node."""
    max_f = 0.0
    for mid, (ni, nj) in enumerate(truss_model.members):
        if ni == node_id or nj == node_id:
            max_f = max(max_f, abs(member_forces[mid]))
    return max_f


def print_check_summary(strut_checks, tie_checks, node_checks):
    """Print formatted summary of all design checks."""
    print("=" * 70)
    print("AASHTO LRFD 5.8.2 DESIGN CHECK SUMMARY")
    print("=" * 70)

    if strut_checks:
        print("\nSTRUT CAPACITY CHECKS (phi = 0.75)")
        print(f"  {'ID':>4}  {'Force':>10}  {'fcu':>8}  {'Capacity':>10}  {'D/C':>6}  {'Status'}")
        print(f"  {'':>4}  {'(kip)':>10}  {'(ksi)':>8}  {'(kip)':>10}  {'':>6}")
        print("  " + "-" * 58)
        for sc in strut_checks:
            print(f"  {sc.member_id:>4}  {sc.force:>+10.1f}  {sc.fcu:>8.3f}  "
                  f"{sc.capacity:>10.1f}  {sc.dc_ratio:>6.3f}  {sc.status}")

    if tie_checks:
        print("\nTIE REINFORCEMENT CHECKS (phi = 0.90)")
        print(f"  {'ID':>4}  {'Force':>10}  {'As_req':>8}  {'As_prov':>8}  "
              f"{'Bars':>10}  {'D/C':>6}  {'Status'}")
        print(f"  {'':>4}  {'(kip)':>10}  {'(in2)':>8}  {'(in2)':>8}  "
              f"{'':>10}  {'':>6}")
        print("  " + "-" * 66)
        for tc in tie_checks:
            bar_str = f"{tc.n_bars}-#{tc.bar_size}"
            print(f"  {tc.member_id:>4}  {tc.force:>+10.1f}  {tc.As_required:>8.3f}  "
                  f"{tc.As_provided:>8.3f}  {bar_str:>10}  {tc.dc_ratio:>6.3f}  {tc.status}")

    if node_checks:
        print("\nNODAL ZONE CHECKS (phi = 0.75)")
        print(f"  {'Node':>4}  {'Type':>5}  {'Force':>10}  {'fcu':>8}  "
              f"{'Capacity':>10}  {'D/C':>6}  {'Status'}")
        print("  " + "-" * 58)
        for nc in node_checks:
            print(f"  {nc.node_id:>4}  {nc.zone_type:>5}  {nc.max_force:>+10.1f}  "
                  f"{nc.fcu_node:>8.3f}  {nc.capacity:>10.1f}  {nc.dc_ratio:>6.3f}  {nc.status}")

    # Overall status
    all_checks = strut_checks + tie_checks + node_checks
    all_ok = all(getattr(c, 'status', 'OK') == 'OK' for c in all_checks)
    print("\n" + "=" * 70)
    print(f"OVERALL: {'ALL CHECKS PASS' if all_ok else 'SOME CHECKS FAIL -- REVISE DESIGN'}")
    print("=" * 70)
