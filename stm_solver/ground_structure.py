"""Discrete ground-structure optimization for pier-cap strut-and-tie models.

This module intentionally deals only with force flow.  Member widths, nodal
zones, anchorage, and code resistance checks belong to later design stages.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from .truss_extract import TrussModel


@dataclass
class GroundStructureResult:
    """Result of a minimum-load-path ground-structure optimization."""

    truss_model: TrussModel
    member_forces: np.ndarray
    reactions: dict
    objective: float
    equilibrium_residual: float
    candidate_count: int
    status: str
    candidate_forces: np.ndarray | None = None
    selected_candidate_indices: np.ndarray | None = None


@dataclass(frozen=True)
class CandidateMemberRecord:
    """Provenance and selection status of one common candidate member."""

    candidate_id: int
    node_i: int
    node_j: int
    category: str
    angle_degrees: float
    selected_combinations: tuple
    rejection_reason: str | None


@dataclass(frozen=True)
class ForceReversal:
    """Common member that carries both tension and compression."""

    candidate_id: int
    node_i: int
    node_j: int
    tension_combinations: tuple
    compression_combinations: tuple
    maximum_tension: float
    maximum_compression: float


@dataclass
class MultiLoadGroundStructureResult:
    """One pruned physical candidate structure solved for every load case."""

    nodes: np.ndarray
    members: np.ndarray
    common_candidate_ids: np.ndarray
    case_results: dict
    candidate_records: tuple
    force_reversals: tuple
    initial_candidate_count: int
    pruning_iterations: int


@dataclass(frozen=True)
class ExternalFace:
    """Finite bearing or foundation face represented in the 2D cap plane.

    The applied load or support reaction remains at ``node_id``, the centroid
    of the face. ``start`` and ``end`` retain the physical face geometry for
    nodal-zone construction and bearing-stress checks.
    """

    kind: str
    source_index: int
    node_id: int
    center: tuple
    start: tuple
    end: tuple
    width: float
    inward_normal: tuple = (0.0, 1.0)
    nodal_node_id: int | None = None


@dataclass
class FrameBoundaryLayout:
    """Discrete node locations derived from a linear boundary stress diagram."""

    tie_x: float
    compression_x: np.ndarray
    compression_block_forces: np.ndarray
    neutral_axis_x: float
    compression_edge: str


def find_member_crossings(nodes, members, *, tolerance=1e-9):
    """Return pairs of members with a non-nodal planar intersection.

    Members that share an endpoint are not crossings. Collinear members are
    left to a separate overlap check because compression fields may
    intentionally share an axis.
    """
    nodes = np.asarray(nodes, dtype=float)
    members = np.asarray(members, dtype=int)
    crossings = []

    def cross_2d(a, b):
        return a[0] * b[1] - a[1] * b[0]

    for first in range(len(members)):
        i, j = members[first]
        p = nodes[i]
        r = nodes[j] - p
        for second in range(first + 1, len(members)):
            k, ell = members[second]
            if len({int(i), int(j), int(k), int(ell)}) < 4:
                continue
            q = nodes[k]
            s = nodes[ell] - q
            denominator = cross_2d(r, s)
            scale = max(1.0, np.linalg.norm(r) * np.linalg.norm(s))
            if abs(denominator) <= tolerance * scale:
                continue
            offset = q - p
            t = cross_2d(offset, s) / denominator
            u = cross_2d(offset, r) / denominator
            if -tolerance <= t <= 1.0 + tolerance and -tolerance <= u <= 1.0 + tolerance:
                crossings.append((first, second))
    return crossings


def locate_linear_frame_boundary(
    section_width,
    thickness,
    neutral_axis_x,
    compression_edge_stress,
    tie_x,
    *,
    edge_partition_forces=(),
    compression_edge="right",
):
    """Locate boundary branches from an FHWA-style linear stress diagram.

    Compression-positive stress varies linearly from zero at ``neutral_axis_x``
    to ``compression_edge_stress`` at the named section edge. Optional partition
    forces are peeled inward from the compression edge; the final branch is the
    resultant of the remaining triangular block. Forces locate the branches but
    do not prescribe the final STM member forces.
    """
    values = (section_width, thickness, compression_edge_stress)
    if any(value <= 0 for value in values):
        raise ValueError("Section width, thickness, and edge stress must be positive")
    if not 0.0 <= tie_x <= section_width or not 0.0 < neutral_axis_x < section_width:
        raise ValueError("Tie and neutral-axis locations must lie within the section")
    if compression_edge not in ("left", "right"):
        raise ValueError("compression_edge must be 'left' or 'right'")

    # Reflect left-edge compression to the same local coordinate system used
    # for right-edge integration, then reflect centroids back at the end.
    reflect = compression_edge == "left"
    na = section_width - neutral_axis_x if reflect else neutral_axis_x
    local_tie = section_width - tie_x if reflect else tie_x
    compression_depth = section_width - na
    total_force = 0.5 * thickness * compression_depth * compression_edge_stress
    requested = np.asarray(edge_partition_forces, dtype=float)
    if np.any(requested <= 0) or requested.sum() >= total_force:
        raise ValueError("Positive partition forces must sum to less than total compression")

    k = compression_edge_stress / compression_depth

    def block_force(a, b):
        return 0.5 * thickness * k * ((b - na) ** 2 - (a - na) ** 2)

    def block_centroid(a, b):
        ua, ub = a - na, b - na
        first = thickness * k * (
            (ub**3 - ua**3) / 3.0 + na * (ub**2 - ua**2) / 2.0
        )
        return first / block_force(a, b)

    centroids = []
    forces = []
    high = section_width
    for target in requested:
        high_u = high - na
        low_u_squared = high_u**2 - 2.0 * target / (thickness * k)
        if low_u_squared < -1e-10:
            raise ValueError("A requested partition exceeds the remaining compression block")
        low = na + np.sqrt(max(0.0, low_u_squared))
        centroids.append(block_centroid(low, high))
        forces.append(block_force(low, high))
        high = low

    remaining = block_force(na, high)
    if remaining > 1e-10:
        centroids.append(block_centroid(na, high))
        forces.append(remaining)

    centroids = np.asarray(centroids)
    if reflect:
        centroids = section_width - centroids
        local_tie = section_width - local_tie
    return FrameBoundaryLayout(
        tie_x=float(local_tie),
        compression_x=centroids,
        compression_block_forces=np.asarray(forces),
        neutral_axis_x=float(neutral_axis_x),
        compression_edge=compression_edge,
    )


def generate_frame_boundary_candidates(
    top_nodes,
    lower_nodes,
    boundary_nodes,
    *,
    min_angle=25.0,
    max_angle=90.0,
):
    """Generate candidates for a cap joined to a column or adjoining B-region.

    ``top_nodes`` and ``lower_nodes`` define potential chord and web nodes
    inside the D-region. Each boundary-node dictionary defines an external
    resultant location and the internal node to which its short boundary
    branch connects::

        {"x": 0.0, "y": -5.0, "connect_group": "top",
         "connect_index": 0}

    The boundary branches are not supports by themselves. Their resultants
    must come from a compatible sectional or global analysis.
    """
    if not top_nodes or not lower_nodes or not boundary_nodes:
        raise ValueError("Top, lower, and boundary node lists must be nonempty")
    if not (0.0 <= min_angle < max_angle <= 90.0):
        raise ValueError("Require 0 <= min_angle < max_angle <= 90 degrees")

    top = np.asarray([
        (node["x"], node["y"]) if isinstance(node, dict) else node for node in top_nodes
    ], dtype=float)
    lower = np.asarray([
        (node["x"], node["y"]) if isinstance(node, dict) else node for node in lower_nodes
    ], dtype=float)
    boundary = np.array([[node["x"], node["y"]] for node in boundary_nodes], dtype=float)
    if any(array.ndim != 2 or array.shape[1] != 2 for array in (top, lower, boundary)):
        raise ValueError("All frame-boundary coordinates must be two-dimensional")

    nodes = np.vstack((top, lower, boundary))
    n_top = len(top)
    n_lower = len(lower)
    members = set()

    def add_member(i, j):
        if i != j:
            members.add((min(i, j), max(i, j)))

    # FHWA guidance favors the fewest practical truss panels. Adjacent chord
    # segments and a complete but angle-limited web let the optimizer make
    # that choice without overlapping long chord members.
    for start, count in ((0, n_top), (n_top, n_lower)):
        ordered = sorted(range(start, start + count), key=lambda nid: nodes[nid, 0])
        for i, j in zip(ordered[:-1], ordered[1:]):
            add_member(i, j)

    for top_id in range(n_top):
        for lower_offset, lower_id in enumerate(range(n_top, n_top + n_lower)):
            lower_definition = lower_nodes[lower_offset]
            if isinstance(lower_definition, dict):
                allowed = lower_definition.get("connect_top_indices")
                if allowed is not None and top_id not in allowed:
                    continue
            delta = nodes[lower_id] - nodes[top_id]
            dx, dy = abs(delta[0]), abs(delta[1])
            if dy <= 1e-10:
                continue
            angle = 90.0 if dx <= 1e-10 else np.degrees(np.arctan2(dy, dx))
            if min_angle <= angle <= max_angle:
                add_member(top_id, lower_id)

    boundary_map = {}
    def resolve_internal(group, connect_index):
        group = group.lower()
        if group == "top":
            if not 0 <= connect_index < n_top:
                raise ValueError("Boundary top-node index is outside the model")
            return connect_index
        elif group == "lower":
            if not 0 <= connect_index < n_lower:
                raise ValueError("Boundary lower-node index is outside the model")
            return n_top + connect_index
        else:
            raise ValueError("connect_group must be 'top' or 'lower'")

    for boundary_index, item in enumerate(boundary_nodes):
        connect_index = int(item["connect_index"])
        internal_id = resolve_internal(item["connect_group"], connect_index)
        terminal_id = n_top + n_lower + boundary_index
        add_member(internal_id, terminal_id)
        for connection in item.get("additional_connections", []):
            add_member(
                resolve_internal(
                    connection["connect_group"], int(connection["connect_index"])
                ),
                terminal_id,
            )
        for other_boundary_index in item.get("connect_boundary_indices", []):
            other_boundary_index = int(other_boundary_index)
            if not 0 <= other_boundary_index < len(boundary_nodes):
                raise ValueError("Connected boundary-node index is outside the model")
            add_member(terminal_id, n_top + n_lower + other_boundary_index)
        boundary_map[boundary_index] = terminal_id

    return nodes, np.asarray(sorted(members), dtype=int), boundary_map


def optimize_frame_boundary(
    top_nodes,
    lower_nodes,
    boundary_nodes,
    top_loads,
    boundary_forces,
    *,
    min_angle=25.0,
    max_angle=90.0,
    tension_weight=1.25,
    compression_weight=1.0,
    force_tolerance=1e-6,
):
    """Optimize a D-region with prescribed resultants at a frame boundary.

    Boundary forces are external nodal forces from the adjoining region. They
    must balance the applied cap loads; unlike pile supports, they are not free
    reactions selected by the optimizer.
    """
    nodes, members, boundary_map = generate_frame_boundary_candidates(
        top_nodes,
        lower_nodes,
        boundary_nodes,
        min_angle=min_angle,
        max_angle=max_angle,
    )
    if len(top_loads) != len(top_nodes):
        raise ValueError("top_loads must contain one force pair per top node")
    if len(boundary_forces) != len(boundary_nodes):
        raise ValueError("boundary_forces must contain one force pair per boundary node")

    nodal_loads = {
        index: tuple(force) for index, force in enumerate(top_loads)
        if np.linalg.norm(force) > 0.0
    }
    for boundary_index, force in enumerate(boundary_forces):
        nodal_loads[boundary_map[boundary_index]] = tuple(force)

    resultant = np.sum(np.asarray(list(nodal_loads.values()), dtype=float), axis=0)
    moment = sum(
        nodes[node_id, 0] * force[1] - nodes[node_id, 1] * force[0]
        for node_id, force in nodal_loads.items()
    )
    force_scale = max(1.0, sum(np.linalg.norm(force) for force in nodal_loads.values()))
    length_scale = max(1.0, float(np.ptp(nodes[:, 0])), float(np.ptp(nodes[:, 1])))
    if np.linalg.norm(resultant) > 1e-8 * force_scale or abs(moment) > 1e-8 * force_scale * length_scale:
        raise ValueError(
            "Applied and frame-boundary forces must be self-equilibrated; "
            f"unbalanced resultant is ({resultant[0]:.6g}, {resultant[1]:.6g}) "
            f"and moment is {moment:.6g}"
        )
    return optimize_ground_structure(
        nodes,
        members,
        nodal_loads,
        constrained_dofs=[],
        tension_weight=tension_weight,
        compression_weight=compression_weight,
        force_tolerance=force_tolerance,
    )


def optimize_frame_boundary_actions(
    top_nodes,
    lower_nodes,
    boundary_nodes,
    top_loads,
    *,
    axial_compression,
    moment_about_reference,
    interface_shear=0.0,
    reference_x=0.0,
    reference_y=0.0,
    min_angle=25.0,
    max_angle=90.0,
    tension_weight=1.25,
    compression_weight=1.0,
    force_tolerance=1e-6,
    boundary_force_targets=None,
):
    """Optimize with boundary branches constrained by section axial force and moment.

    This formulation leaves the individual boundary-branch forces unknown while
    requiring their horizontal resultant, vertical resultant, and moment to
    match the adjoining section. Positive interface shear acts in +x; positive
    axial compression acts in +y.
    """
    if axial_compression <= 0:
        raise ValueError("axial_compression must be positive")
    nodes, members, boundary_map = generate_frame_boundary_candidates(
        top_nodes,
        lower_nodes,
        boundary_nodes,
        min_angle=min_angle,
        max_angle=max_angle,
    )
    if len(top_loads) != len(top_nodes):
        raise ValueError("top_loads must contain one force pair per top node")
    if boundary_force_targets is None and len(lower_nodes) > 1:
        missing_correspondence = [
            index for index, node in enumerate(lower_nodes)
            if not isinstance(node, dict) or node.get("connect_top_indices") is None
        ]
        if missing_correspondence:
            raise ValueError(
                "Multiple compression branches require explicit load correspondence "
                f"for lower nodes {missing_correspondence}"
            )

    n_top = len(top_nodes)
    boundary_member_ids = []
    for boundary_index, item in enumerate(boundary_nodes):
        terminal = boundary_map[boundary_index]
        if item["connect_group"].lower() == "top":
            internal = int(item["connect_index"])
        else:
            internal = n_top + int(item["connect_index"])
        pair = (min(internal, terminal), max(internal, terminal))
        boundary_member_ids.append(next(
            mid for mid, member in enumerate(members) if tuple(member) == pair
        ))

    # A boundary member contributes N*d to the D-region at its internal node,
    # where d points from that internal node toward the boundary terminal.
    # Constrain the vector resultant and its moment about the reference point.
    force_matrix = np.zeros((3, len(members)))
    for mid, boundary_index in zip(boundary_member_ids, range(len(boundary_nodes))):
        terminal = boundary_map[boundary_index]
        ni, nj = members[mid]
        internal = ni if nj == terminal else nj
        delta = nodes[terminal] - nodes[internal]
        direction = delta / np.linalg.norm(delta)
        rx = nodes[internal, 0] - reference_x
        ry = nodes[internal, 1] - reference_y
        force_matrix[0, mid] = direction[0]
        force_matrix[1, mid] = direction[1]
        force_matrix[2, mid] = rx * direction[1] - ry * direction[0]
    force_rhs = np.array(
        [interface_shear, axial_compression, moment_about_reference], dtype=float
    )
    if boundary_force_targets is not None:
        if len(boundary_force_targets) != len(boundary_nodes):
            raise ValueError("boundary_force_targets must align with boundary_nodes")
        extra_rows = []
        extra_rhs = []
        for mid, target in zip(boundary_member_ids, boundary_force_targets):
            if target is None:
                continue
            row = np.zeros(len(members))
            row[mid] = 1.0
            extra_rows.append(row)
            extra_rhs.append(float(target))
        if extra_rows:
            force_matrix = np.vstack((force_matrix, extra_rows))
            force_rhs = np.concatenate((force_rhs, extra_rhs))

    nodal_loads = {
        index: tuple(force) for index, force in enumerate(top_loads)
        if np.linalg.norm(force) > 0.0
    }
    constrained_dofs = [
        dof
        for terminal in boundary_map.values()
        for dof in (2 * terminal, 2 * terminal + 1)
    ]
    return optimize_ground_structure(
        nodes,
        members,
        nodal_loads,
        constrained_dofs,
        tension_weight=tension_weight,
        compression_weight=compression_weight,
        force_tolerance=force_tolerance,
        member_force_equalities=(force_matrix, force_rhs),
    )


def optimize_frame_boundary_load_cases(
    top_nodes,
    lower_nodes,
    boundary_nodes,
    load_cases,
    *,
    boundary_member_targets=None,
    target_relative_tolerance=0.0,
    min_angle=25.0,
    max_angle=90.0,
    tension_weight=1.25,
    compression_weight=1.0,
    force_tolerance=1e-6,
    diagonal_webs_compression_only=True,
):
    """Solve frame-boundary D-region cases on one generated candidate model.

    Loads identify nodes by their ``id`` values. Boundary-member targets are
    optional reviewed sectional-analysis results keyed by pairs of node IDs;
    they constrain only the interface branches and leave the D-region force
    flow to the optimizer.
    """
    nodes, members, boundary_map = generate_frame_boundary_candidates(
        top_nodes, lower_nodes, boundary_nodes,
        min_angle=min_angle, max_angle=max_angle,
    )
    definitions = list(top_nodes) + list(lower_nodes) + list(boundary_nodes)
    node_ids = [item.get("id") if isinstance(item, dict) else None for item in definitions]
    if any(node_id is None for node_id in node_ids) or len(set(node_ids)) != len(node_ids):
        raise ValueError("Every frame node requires a unique id")
    node_lookup = {node_id: index for index, node_id in enumerate(node_ids)}
    candidate_lookup = {
        tuple(sorted((int(i), int(j)))): index for index, (i, j) in enumerate(members)
    }
    constrained_dofs = [
        dof for terminal in boundary_map.values()
        for dof in (2 * terminal, 2 * terminal + 1)
    ]
    targets_by_case = boundary_member_targets or {}

    def solve_case(name, loads):
        nodal_loads = {}
        for load in loads:
            node_id = load["node"]
            if node_id not in node_lookup:
                raise ValueError(f"Unknown frame node id: {node_id!r}")
            nodal_loads[node_lookup[node_id]] = (
                float(load.get("Px", 0.0)), float(load.get("Py", 0.0)),
            )
        bounds = {}
        if diagonal_webs_compression_only:
            n_top = len(top_nodes)
            n_lower = len(lower_nodes)
            for member_index, (i, j) in enumerate(members):
                web = (
                    (i < n_top and n_top <= j < n_top + n_lower)
                    or (j < n_top and n_top <= i < n_top + n_lower)
                )
                if web and not np.isclose(nodes[i, 0], nodes[j, 0]):
                    bounds[member_index] = (-np.inf, 0.0)
        case_targets = targets_by_case.get(name, targets_by_case.get("*", ()))
        for target in case_targets:
            pair = tuple(sorted((node_lookup[target["i"]], node_lookup[target["j"]])))
            if pair not in candidate_lookup:
                raise ValueError(f"Targeted boundary member {target['i']}-{target['j']} is not a candidate")
            value = float(target["force"])
            delta = float(target_relative_tolerance) * max(abs(value), 1.0)
            bounds[candidate_lookup[pair]] = (value - delta, value + delta)
        return optimize_ground_structure(
            nodes, members, nodal_loads, constrained_dofs,
            tension_weight=tension_weight, compression_weight=compression_weight,
            force_tolerance=force_tolerance,
            member_force_bounds=bounds or None,
        )

    cases = {str(name): list(loads) for name, loads in dict(load_cases).items()}
    if not cases:
        raise ValueError("At least one frame-boundary load case is required")
    case_results = {name: solve_case(name, loads) for name, loads in cases.items()}
    names = tuple(case_results)
    force_matrix = np.vstack([result.candidate_forces for result in case_results.values()])
    scale = max(1.0, float(np.max(np.abs(force_matrix))))
    active_tolerance = force_tolerance * scale
    records = []
    reversals = []
    for candidate_id, (i, j) in enumerate(members):
        forces = force_matrix[:, candidate_id]
        tension_cases = tuple(name for name, force in zip(names, forces) if force > active_tolerance)
        compression_cases = tuple(name for name, force in zip(names, forces) if force < -active_tolerance)
        delta = nodes[j] - nodes[i]
        if np.isclose(delta[1], 0.0):
            category = "chord"
        elif i >= len(top_nodes) + len(lower_nodes) or j >= len(top_nodes) + len(lower_nodes):
            category = "boundary_transfer"
        elif np.isclose(delta[0], 0.0):
            category = "vertical"
        else:
            category = "diagonal_web"
        records.append(CandidateMemberRecord(
            candidate_id=candidate_id, node_i=int(i), node_j=int(j),
            category=category,
            angle_degrees=float(np.degrees(np.arctan2(abs(delta[1]), abs(delta[0])))),
            selected_combinations=tension_cases + compression_cases,
            rejection_reason=(None if tension_cases or compression_cases else "zero force in every load case"),
        ))
        if tension_cases and compression_cases:
            reversals.append(ForceReversal(
                candidate_id=candidate_id, node_i=int(i), node_j=int(j),
                tension_combinations=tension_cases,
                compression_combinations=compression_cases,
                maximum_tension=float(np.max(forces)),
                maximum_compression=float(np.min(forces)),
            ))
    return MultiLoadGroundStructureResult(
        nodes=nodes.copy(), members=members.copy(),
        common_candidate_ids=np.arange(len(members)),
        case_results=case_results, candidate_records=tuple(records),
        force_reversals=tuple(reversals), initial_candidate_count=len(members),
        pruning_iterations=0,
    )


def generate_pier_cap_candidates(
    loads,
    piles,
    *,
    top_tie_y=None,
    bottom_tie_y=None,
    min_angle=20.0,
    max_angle=75.0,
    include_verticals=True,
):
    """Generate a compact, physically meaningful pier-cap ground structure.

    Nodes are placed at bearing resultants, pile resultants, and at their
    projections onto the top and bottom reinforcement centrelines. Candidate
    members comprise chord segments and admissible top-to-bottom members.

    Parameters
    ----------
    loads, piles : list of dict
        Each item requires ``x`` and ``y``. Loads additionally use ``Px`` and
        ``Py`` during optimization. Piles use the same support types as the
        existing solver (``pin``, ``fixed``, or ``roller``).
    top_tie_y, bottom_tie_y : float, optional
        Reinforcement centrelines. Defaults to the load and pile elevations.
    min_angle, max_angle : float
        Permitted angle from horizontal for nonvertical web members.

    Returns
    -------
    nodes, members, load_node_ids, pile_node_ids
    """
    if not loads or not piles:
        raise ValueError("At least one bearing load and one pile are required")
    if not (0.0 <= min_angle < max_angle <= 90.0):
        raise ValueError("Require 0 <= min_angle < max_angle <= 90 degrees")

    if top_tie_y is None:
        top_tie_y = max(float(load["y"]) for load in loads)
    if bottom_tie_y is None:
        bottom_tie_y = min(float(pile["y"]) for pile in piles)
    if top_tie_y <= bottom_tie_y:
        raise ValueError("top_tie_y must be above bottom_tie_y")

    node_list = []

    def add_node(x, y):
        point = np.array([float(x), float(y)])
        for nid, existing in enumerate(node_list):
            if np.linalg.norm(existing - point) <= 1e-8:
                return nid
        node_list.append(point)
        return len(node_list) - 1

    load_node_ids = {
        i: add_node(load["x"], load["y"]) for i, load in enumerate(loads)
    }
    pile_node_ids = {
        i: add_node(pile["x"], pile["y"]) for i, pile in enumerate(piles)
    }

    top_projection_ids = [add_node(item["x"], top_tie_y) for item in loads + piles]
    bottom_projection_ids = [add_node(item["x"], bottom_tie_y) for item in loads + piles]
    top_ids = set(top_projection_ids)
    bottom_ids = set(bottom_projection_ids)

    members = set()

    def add_member(i, j):
        if i != j:
            members.add((min(i, j), max(i, j)))

    # Transfer finite-face resultants to the reinforcement-centreline model.
    # These short verticals are explicit candidates rather than hidden offsets.
    for load_index, load_node in load_node_ids.items():
        add_member(load_node, top_projection_ids[load_index])
    pile_offset = len(loads)
    for pile_index, pile_node in pile_node_ids.items():
        add_member(pile_node, bottom_projection_ids[pile_offset + pile_index])

    # Chord segments are restricted to adjacent nodes so the reported model
    # does not contain several overlapping representations of the same tie.
    for chord_ids in (top_ids, bottom_ids):
        ordered = sorted(chord_ids, key=lambda nid: node_list[nid][0])
        for i, j in zip(ordered[:-1], ordered[1:]):
            add_member(i, j)

    for i in top_ids:
        for j in bottom_ids:
            dx = abs(node_list[j][0] - node_list[i][0])
            dy = abs(node_list[j][1] - node_list[i][1])
            if dy <= 1e-9:
                continue
            if dx <= 1e-9:
                if include_verticals:
                    add_member(i, j)
                continue
            angle = np.degrees(np.arctan2(dy, dx))
            if min_angle <= angle <= max_angle:
                add_member(i, j)

    if not members:
        raise ValueError("Candidate-generation rules produced no members")

    return (
        np.asarray(node_list, dtype=float),
        np.asarray(sorted(members), dtype=int),
        load_node_ids,
        pile_node_ids,
    )


def build_pier_cap_external_faces(
    loads, piles, load_node_ids, pile_node_ids, *, truss_model=None,
):
    """Build finite horizontal faces for bearings and pile/shaft heads.

    Face width is optional to retain compatibility with point-resultant input.
    Load faces accept ``face_width`` or ``bearing_width``. Foundation faces
    accept ``face_width`` or ``diameter``; ``foundation_type='shaft'`` labels a
    shaft head, otherwise the face is labeled as a pile head.
    """
    faces = []

    def resolve_nodal_node(node_id):
        if truss_model is None:
            return node_id
        connected = [
            int(j if i == node_id else i)
            for i, j in truss_model.members
            if node_id in (i, j)
        ]
        if len(connected) != 1:
            return node_id
        other = connected[0]
        start = np.asarray(truss_model.nodes[node_id], dtype=float)
        end = np.asarray(truss_model.nodes[other], dtype=float)
        return other if np.isclose(start[0], end[0]) else node_id

    def add_face(item, source_index, node_id, kind, width_keys, inward_normal):
        supplied = [key for key in width_keys if item.get(key) is not None]
        if not supplied:
            return
        width = float(item[supplied[0]])
        if not np.isfinite(width) or width <= 0.0:
            raise ValueError(f"{kind} face width must be a positive finite value")
        x = float(item["x"])
        y = float(item["y"])
        half_width = 0.5 * width
        faces.append(ExternalFace(
            kind=kind,
            source_index=source_index,
            node_id=node_id,
            center=(x, y),
            start=(x - half_width, y),
            end=(x + half_width, y),
            width=width,
            inward_normal=inward_normal,
            nodal_node_id=resolve_nodal_node(node_id),
        ))

    for index, load in enumerate(loads):
        add_face(
            load, index, load_node_ids[index], "bearing_plate",
            ("face_width", "bearing_width"), (0.0, -1.0),
        )
    for index, pile in enumerate(piles):
        foundation_type = str(pile.get("foundation_type", "pile")).lower()
        if foundation_type not in ("pile", "shaft"):
            raise ValueError(
                "foundation_type must be either 'pile' or 'shaft'"
            )
        add_face(
            pile, index, pile_node_ids[index], f"{foundation_type}_head",
            ("face_width", "diameter"), (0.0, 1.0),
        )
    return faces


def optimize_ground_structure(
    nodes,
    members,
    nodal_loads,
    constrained_dofs,
    *,
    tension_weight=1.25,
    compression_weight=1.0,
    force_tolerance=1e-6,
    member_force_equalities=None,
    member_force_bounds=None,
):
    """Find a minimum-load-path statically admissible truss.

    Positive member force denotes tension and negative force denotes
    compression. Separate nonnegative tension and compression variables make
    the problem a linear program.
    """
    nodes = np.asarray(nodes, dtype=float)
    members = np.asarray(members, dtype=int)
    if nodes.ndim != 2 or nodes.shape[1] != 2:
        raise ValueError("nodes must have shape (n, 2)")
    if members.ndim != 2 or members.shape[1] != 2:
        raise ValueError("members must have shape (m, 2)")
    if tension_weight <= 0 or compression_weight <= 0:
        raise ValueError("Objective weights must be positive")

    n_nodes = len(nodes)
    n_members = len(members)
    n_dofs = 2 * n_nodes
    B = np.zeros((n_dofs, n_members))
    lengths = np.zeros(n_members)

    for mid, (ni, nj) in enumerate(members):
        delta = nodes[nj] - nodes[ni]
        length = np.linalg.norm(delta)
        if length <= 1e-10:
            raise ValueError(f"Candidate member {mid} has zero length")
        direction = delta / length
        B[2 * ni:2 * ni + 2, mid] = direction
        B[2 * nj:2 * nj + 2, mid] = -direction
        lengths[mid] = length

    P = np.zeros(n_dofs)
    for nid, force in nodal_loads.items():
        P[2 * nid:2 * nid + 2] += np.asarray(force, dtype=float)

    constrained = np.asarray(sorted(set(constrained_dofs)), dtype=int)
    if np.any((constrained < 0) | (constrained >= n_dofs)):
        raise ValueError("A constrained DOF lies outside the model")
    free = np.setdiff1d(np.arange(n_dofs), constrained)

    # N = T - C; equilibrium at free DOFs is B*N + P = 0.
    A_eq = np.hstack((B[free], -B[free]))
    b_eq = -P[free]
    if member_force_equalities is not None:
        force_matrix, force_rhs = member_force_equalities
        force_matrix = np.asarray(force_matrix, dtype=float)
        force_rhs = np.asarray(force_rhs, dtype=float)
        if force_matrix.ndim != 2 or force_matrix.shape[1] != n_members:
            raise ValueError("Member-force equality matrix must have one column per member")
        if force_rhs.shape != (force_matrix.shape[0],):
            raise ValueError("Member-force equality right-hand side has the wrong shape")
        A_eq = np.vstack((A_eq, np.hstack((force_matrix, -force_matrix))))
        b_eq = np.concatenate((b_eq, force_rhs))
    A_ub = None
    b_ub = None
    if member_force_bounds:
        bound_rows = []
        bound_rhs = []
        for member_index, (lower, upper) in member_force_bounds.items():
            if not 0 <= member_index < n_members:
                raise ValueError("A member-force bound references an unknown member")
            if lower > upper:
                raise ValueError("A member-force lower bound exceeds its upper bound")
            row = np.zeros(2 * n_members)
            row[member_index] = 1.0
            row[n_members + member_index] = -1.0
            if np.isfinite(upper):
                bound_rows.append(row)
                bound_rhs.append(float(upper))
            if np.isfinite(lower):
                bound_rows.append(-row)
                bound_rhs.append(float(-lower))
        if bound_rows:
            A_ub = np.asarray(bound_rows)
            b_ub = np.asarray(bound_rhs)
    objective = np.concatenate(
        (tension_weight * lengths, compression_weight * lengths)
    )
    solution = linprog(
        objective,
        A_eq=A_eq,
        b_eq=b_eq,
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=(0.0, None),
        method="highs",
    )
    if not solution.success:
        raise ValueError(f"No admissible ground-structure solution: {solution.message}")

    forces = solution.x[:n_members] - solution.x[n_members:]
    scale = max(1.0, float(np.max(np.abs(forces))))
    selected = np.abs(forces) > force_tolerance * scale
    selected_members = members[selected]
    selected_forces = forces[selected]
    member_types = ["tie" if force > 0 else "strut" for force in selected_forces]

    internal_plus_load = B @ forces + P
    reactions = {
        int(dof): float(-internal_plus_load[dof]) for dof in constrained
    }
    residual = float(np.max(np.abs(internal_plus_load[free]))) if len(free) else 0.0

    truss = TrussModel(
        nodes=nodes.copy(),
        members=selected_members.copy(),
        member_types=member_types,
        support_node_ids={},
        load_node_ids={},
    )
    return GroundStructureResult(
        truss_model=truss,
        member_forces=selected_forces,
        reactions=reactions,
        objective=float(solution.fun),
        equilibrium_residual=residual,
        candidate_count=n_members,
        status=solution.message,
        candidate_forces=forces.copy(),
        selected_candidate_indices=np.flatnonzero(selected),
    )


def optimize_pier_cap(
    loads,
    piles,
    *,
    top_tie_y=None,
    bottom_tie_y=None,
    min_angle=20.0,
    max_angle=75.0,
    tension_weight=1.25,
    compression_weight=1.0,
    force_tolerance=1e-6,
    diagonal_webs_compression_only=True,
):
    """Generate and optimize a two-dimensional pile-supported pier-cap STM."""
    resolved_top_tie_y = (
        max(float(load["y"]) for load in loads) if top_tie_y is None else top_tie_y
    )
    resolved_bottom_tie_y = (
        min(float(pile["y"]) for pile in piles)
        if bottom_tie_y is None else bottom_tie_y
    )
    nodes, members, load_ids, pile_ids = generate_pier_cap_candidates(
        loads,
        piles,
        top_tie_y=resolved_top_tie_y,
        bottom_tie_y=resolved_bottom_tie_y,
        min_angle=min_angle,
        max_angle=max_angle,
    )
    nodal_loads = {
        load_ids[i]: (float(load.get("Px", 0.0)), float(load.get("Py", 0.0)))
        for i, load in enumerate(loads)
    }
    constrained_dofs = []
    for i, pile in enumerate(piles):
        nid = pile_ids[i]
        support_type = pile.get("type", "roller").lower()
        if support_type in ("pin", "fixed"):
            constrained_dofs.extend((2 * nid, 2 * nid + 1))
        elif support_type == "roller":
            constrained_dofs.append(2 * nid + 1)
        else:
            raise ValueError(f"Unknown pile support type: {support_type!r}")

    member_force_bounds = None
    if diagonal_webs_compression_only:
        member_force_bounds = {}
        for member_index, (i, j) in enumerate(members):
            yi, yj = nodes[i, 1], nodes[j, 1]
            is_top_bottom_web = (
                (np.isclose(yi, resolved_top_tie_y)
                 and np.isclose(yj, resolved_bottom_tie_y))
                or (np.isclose(yj, resolved_top_tie_y)
                    and np.isclose(yi, resolved_bottom_tie_y))
            )
            if is_top_bottom_web and not np.isclose(nodes[i, 0], nodes[j, 0]):
                member_force_bounds[member_index] = (-np.inf, 0.0)

    result = optimize_ground_structure(
        nodes,
        members,
        nodal_loads,
        constrained_dofs,
        tension_weight=tension_weight,
        compression_weight=compression_weight,
        force_tolerance=force_tolerance,
        member_force_bounds=member_force_bounds,
    )
    result.truss_model.load_node_ids = load_ids
    result.truss_model.support_node_ids = pile_ids
    result.truss_model.external_faces = build_pier_cap_external_faces(
        loads, piles, load_ids, pile_ids, truss_model=result.truss_model,
    )
    return result


def optimize_pier_cap_load_cases(
    load_cases,
    piles,
    *,
    top_tie_y=None,
    bottom_tie_y=None,
    min_angle=20.0,
    max_angle=75.0,
    tension_weight=1.25,
    compression_weight=1.0,
    force_tolerance=1e-6,
    diagonal_webs_compression_only=True,
    maximum_pruning_iterations=10,
):
    """Solve multiple cases on one iteratively pruned physical ground structure.

    A complete candidate set is generated once from common load/support
    locations. Each case is solved, candidates unused by every case are removed,
    and all cases are re-solved until the common set is stable. Returned case
    results retain their selected members for downstream design, while
    ``candidate_forces`` aligns with the common ``members`` array.
    """
    cases = {str(name): list(loads) for name, loads in dict(load_cases).items()}
    if not cases:
        raise ValueError("At least one load case is required")
    if not piles:
        raise ValueError("At least one pile is required")
    maximum_pruning_iterations = int(maximum_pruning_iterations)
    if maximum_pruning_iterations < 1:
        raise ValueError("maximum_pruning_iterations must be at least one")

    first_name = next(iter(cases))
    reference_loads = cases[first_name]
    if not reference_loads:
        raise ValueError("Every load case requires at least one load")

    def physical_signature(load):
        width = load.get("face_width", load.get("bearing_width"))
        return (
            load.get("id"), float(load["x"]), float(load["y"]),
            None if width is None else float(width),
        )

    reference_signature = tuple(map(physical_signature, reference_loads))
    for name, loads in cases.items():
        if tuple(map(physical_signature, loads)) != reference_signature:
            raise ValueError(
                f"Load case {name!r} does not use the common load locations and faces"
            )

    resolved_top = (
        max(float(load["y"]) for load in reference_loads)
        if top_tie_y is None else float(top_tie_y)
    )
    resolved_bottom = (
        min(float(pile["y"]) for pile in piles)
        if bottom_tie_y is None else float(bottom_tie_y)
    )
    nodes, all_members, load_ids, pile_ids = generate_pier_cap_candidates(
        reference_loads, piles, top_tie_y=resolved_top,
        bottom_tie_y=resolved_bottom, min_angle=min_angle, max_angle=max_angle,
    )
    initial_candidate_count = len(all_members)

    constrained_dofs = []
    for index, pile in enumerate(piles):
        node_id = pile_ids[index]
        support_type = pile.get("type", "roller").lower()
        if support_type in ("pin", "fixed"):
            constrained_dofs.extend((2 * node_id, 2 * node_id + 1))
        elif support_type == "roller":
            constrained_dofs.append(2 * node_id + 1)
        else:
            raise ValueError(f"Unknown pile support type: {support_type!r}")

    def solve_case(loads, members):
        bounds = None
        if diagonal_webs_compression_only:
            bounds = {}
            for member_index, (i, j) in enumerate(members):
                yi, yj = nodes[i, 1], nodes[j, 1]
                web = (
                    (np.isclose(yi, resolved_top) and np.isclose(yj, resolved_bottom))
                    or (np.isclose(yj, resolved_top)
                        and np.isclose(yi, resolved_bottom))
                )
                if web and not np.isclose(nodes[i, 0], nodes[j, 0]):
                    bounds[member_index] = (-np.inf, 0.0)
        nodal_loads = {
            load_ids[index]: (
                float(load.get("Px", 0.0)), float(load.get("Py", 0.0)),
            )
            for index, load in enumerate(loads)
        }
        result = optimize_ground_structure(
            nodes, members, nodal_loads, constrained_dofs,
            tension_weight=tension_weight, compression_weight=compression_weight,
            force_tolerance=force_tolerance, member_force_bounds=bounds,
        )
        result.truss_model.load_node_ids = load_ids.copy()
        result.truss_model.support_node_ids = pile_ids.copy()
        result.truss_model.external_faces = build_pier_cap_external_faces(
            loads, piles, load_ids, pile_ids, truss_model=result.truss_model,
        )
        return result

    common_members = all_members.copy()
    common_original_indices = np.arange(initial_candidate_count)
    pruning_iterations = 0
    for iteration in range(maximum_pruning_iterations):
        trial_results = {
            name: solve_case(loads, common_members)
            for name, loads in cases.items()
        }
        used = np.zeros(len(common_members), dtype=bool)
        for result in trial_results.values():
            used[result.selected_candidate_indices] = True
        if np.all(used):
            pruning_iterations = iteration
            break
        common_members = common_members[used]
        common_original_indices = common_original_indices[used]
        pruning_iterations = iteration + 1
    else:
        raise RuntimeError("Common-member pruning did not converge")

    case_results = {
        name: solve_case(loads, common_members) for name, loads in cases.items()
    }
    force_matrix = np.vstack([
        result.candidate_forces for result in case_results.values()
    ])
    scale = max(1.0, float(np.max(np.abs(force_matrix))))
    active_tolerance = force_tolerance * scale
    names = tuple(case_results)
    reversals = []
    records = []
    common_lookup = {
        int(original): local
        for local, original in enumerate(common_original_indices)
    }
    for candidate_id, (i, j) in enumerate(all_members):
        local_id = common_lookup.get(candidate_id)
        forces = (
            np.zeros(len(names)) if local_id is None
            else force_matrix[:, local_id]
        )
        tension_cases = tuple(
            name for name, force in zip(names, forces) if force > active_tolerance
        )
        compression_cases = tuple(
            name for name, force in zip(names, forces) if force < -active_tolerance
        )
        selected_cases = tension_cases + compression_cases
        delta = nodes[j] - nodes[i]
        angle = float(np.degrees(np.arctan2(abs(delta[1]), abs(delta[0]))))
        if np.isclose(delta[1], 0.0):
            category = "chord"
        elif np.isclose(delta[0], 0.0):
            category = "vertical"
        elif ({nodes[i, 1], nodes[j, 1]}
              == {resolved_top, resolved_bottom}):
            category = "diagonal_web"
        else:
            category = "face_transfer"
        records.append(CandidateMemberRecord(
            candidate_id=candidate_id, node_i=int(i), node_j=int(j),
            category=category, angle_degrees=angle,
            selected_combinations=selected_cases,
            rejection_reason=(
                "zero force in every load case after equilibrium re-solution"
                if local_id is None else None
            ),
        ))
        if tension_cases and compression_cases:
            reversals.append(ForceReversal(
                candidate_id=candidate_id, node_i=int(i), node_j=int(j),
                tension_combinations=tension_cases,
                compression_combinations=compression_cases,
                maximum_tension=float(np.max(forces)),
                maximum_compression=float(np.min(forces)),
            ))

    return MultiLoadGroundStructureResult(
        nodes=nodes.copy(), members=common_members.copy(),
        common_candidate_ids=common_original_indices.copy(),
        case_results=case_results, candidate_records=tuple(records),
        force_reversals=tuple(reversals),
        initial_candidate_count=initial_candidate_count,
        pruning_iterations=pruning_iterations,
    )
