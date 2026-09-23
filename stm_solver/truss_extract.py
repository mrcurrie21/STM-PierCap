"""Truss extraction from BESO topology via chord construction and panel diagonals."""

from dataclasses import dataclass, field

import numpy as np

from .mesh import element_centroids


@dataclass
class TrussModel:
    """Extracted truss model from BESO topology."""

    nodes: np.ndarray  # (n, 2) coordinates
    members: np.ndarray  # (m, 2) node index pairs
    member_types: list  # 'strut' or 'tie' per member
    support_node_ids: dict  # support index -> truss node index
    load_node_ids: dict  # load index -> truss node index
    member_widths: np.ndarray = field(
        default_factory=lambda: np.array([])
    )  # estimated width per member
    external_faces: list = field(default_factory=list)
    # Finite load/support faces associated with external resultant nodes.


def active_to_grid_image(elems, active, classification, nodes, nx, ny):
    """
    Convert active element arrays to 2D grid images.

    Parameters
    ----------
    elems : (n_elems, 4) connectivity
    active : (n_elems,) bool
    classification : (n_elems,) int (0=inactive, 1=strut, 2=tie, 3=mixed)
    nodes : (n_nodes, 2) coordinates
    nx, ny : grid dimensions (number of elements in x and y)

    Returns
    -------
    active_grid : (ny, nx) bool array
    class_grid : (ny, nx) int array
    """
    cx, cy = element_centroids(nodes, elems)

    x_unique = np.unique(np.round(cx, 6))
    y_unique = np.unique(np.round(cy, 6))

    active_grid = np.zeros((ny, nx), dtype=bool)
    class_grid = np.zeros((ny, nx), dtype=int)

    for eid in range(len(elems)):
        ix = np.searchsorted(x_unique, round(cx[eid], 6))
        iy = np.searchsorted(y_unique, round(cy[eid], 6))
        if ix < nx and iy < ny:
            active_grid[iy, ix] = active[eid]
            class_grid[iy, ix] = classification[eid]

    return active_grid, class_grid


def _add_node(node_list, x, y, tol=0.5):
    """Add a node at (x, y) or return the index of an existing nearby node."""
    for idx, (nx, ny) in enumerate(node_list):
        if abs(nx - x) < tol and abs(ny - y) < tol:
            return idx
    new_idx = len(node_list)
    node_list.append([x, y])
    return new_idx


def _sample_strut_density(p1, p2, class_grid, x_unique, y_unique, n_samples=20):
    """Count strut-classified grid cells along a line from p1 to p2."""
    count = 0
    ny_g, nx_g = class_grid.shape
    for i in range(n_samples):
        t = (i + 0.5) / n_samples
        px = p1[0] * (1 - t) + p2[0] * t
        py = p1[1] * (1 - t) + p2[1] * t
        ix = np.searchsorted(x_unique, px)
        iy = np.searchsorted(y_unique, py)
        ix = max(0, min(ix, nx_g - 1))
        iy = max(0, min(iy, ny_g - 1))
        if class_grid[iy, ix] in (1, 3):
            count += 1
    return count


def _classify_member(node_i, node_j, class_grid, x_unique, y_unique):
    """
    Classify a truss member as 'strut' or 'tie' based on the dominant
    classification of elements along its path.
    """
    n_samples = 20
    strut_count = 0
    tie_count = 0
    ny_g, nx_g = class_grid.shape

    for i in range(n_samples):
        t = (i + 0.5) / n_samples
        px = node_i[0] * (1 - t) + node_j[0] * t
        py = node_i[1] * (1 - t) + node_j[1] * t

        ix = np.searchsorted(x_unique, px)
        iy = np.searchsorted(y_unique, py)
        ix = max(0, min(ix, nx_g - 1))
        iy = max(0, min(iy, ny_g - 1))

        cls = class_grid[iy, ix]
        if cls in (1, 3):
            strut_count += 1
        elif cls == 2:
            tie_count += 1

    return "tie" if tie_count > strut_count else "strut"


def _estimate_member_width(node_i, node_j, active_grid, x_unique, y_unique):
    """
    Estimate the width of a member by measuring the active region thickness
    perpendicular to the member at its midpoint.
    """
    mid_x = 0.5 * (node_i[0] + node_j[0])
    mid_y = 0.5 * (node_i[1] + node_j[1])

    dx = node_j[0] - node_i[0]
    dy = node_j[1] - node_i[1]
    length = np.hypot(dx, dy)
    if length < 1e-10:
        return 1.0

    perp_x = -dy / length
    perp_y = dx / length

    grid_dx = x_unique[1] - x_unique[0] if len(x_unique) > 1 else 1.0
    grid_dy = y_unique[1] - y_unique[0] if len(y_unique) > 1 else 1.0
    grid_size = min(grid_dx, grid_dy)

    width = 0.0
    for direction in [1.0, -1.0]:
        for step in range(1, 200):
            px = mid_x + direction * step * grid_size * perp_x
            py = mid_y + direction * step * grid_size * perp_y

            ix = np.searchsorted(x_unique, px)
            iy = np.searchsorted(y_unique, py)
            ix = max(0, min(ix, active_grid.shape[1] - 1))
            iy = max(0, min(iy, active_grid.shape[0] - 1))

            if not active_grid[iy, ix]:
                width += step * grid_size
                break
        else:
            width += 200 * grid_size

    return max(width, grid_size)


# Angle limits for diagonal struts (AASHTO STM guidance)
_MIN_STRUT_ANGLE = 25.0
_MAX_STRUT_ANGLE = 65.0
_MIN_PANEL_DIAG_DENSITY = 6  # min strut hits (of 20 samples) to add a panel diagonal


def extract_truss(
    nodes_fem,
    elems,
    active,
    classification,
    supports,
    loads,
    support_node_ids_fem,
    load_node_ids_fem,
    merge_radius_px=5,
    min_member_length=5.0,
):
    """
    Extract STM truss from BESO results using chord construction and panel diagonals.

    Nodes are placed at support and load application points.  Load x-coordinates
    are projected to the bottom chord to form panel boundaries.  Horizontal
    chords, verticals, and BESO-guided panel diagonals complete the truss.

    Parameters
    ----------
    nodes_fem : (n_nodes, 2) FEM node coordinates
    elems : (n_elems, 4) element connectivity
    active : (n_elems,) bool array
    classification : (n_elems,) int (0=inactive, 1=strut, 2=tie, 3=mixed)
    supports : list of support dicts
    loads : list of load dicts
    support_node_ids_fem : {i: node_id} FEM support node mapping
    load_node_ids_fem : {i: node_id} FEM load node mapping
    merge_radius_px : unused (kept for API compatibility)
    min_member_length : minimum physical member length (in)

    Returns
    -------
    TrussModel
    """
    cx, cy = element_centroids(nodes_fem, elems)
    x_unique = np.unique(np.round(cx, 6))
    y_unique = np.unique(np.round(cy, 6))
    nx_grid = len(x_unique)
    ny_grid = len(y_unique)

    active_grid, class_grid = active_to_grid_image(
        elems, active, classification, nodes_fem, nx_grid, ny_grid
    )

    # Chord elevations from boundary positions
    y_bot = min(s["y"] for s in supports)
    y_top = max(lp["y"] for lp in loads)

    if abs(y_top - y_bot) < 1e-6:
        return _fallback_truss(supports, loads)

    # ── Node placement ───────────────────────────────────────────────
    node_list = []  # [[x, y], ...]
    support_map = {}
    load_map = {}

    for si, s in enumerate(supports):
        support_map[si] = _add_node(node_list, s["x"], s["y"])

    for li, lp in enumerate(loads):
        load_map[li] = _add_node(node_list, lp["x"], lp["y"])

    # Project load x-coordinates to bottom chord (interior bottom nodes)
    load_bot = {}
    for li, lp in enumerate(loads):
        load_bot[li] = _add_node(node_list, lp["x"], y_bot)

    # Check if each support connects directly to at least one load via
    # a diagonal with a valid strut angle.  If not, add a top-chord node
    # above the support so it can participate in the truss via a vertical.
    support_top = {}
    for si, s in enumerate(supports):
        has_diagonal = False
        for lp in loads:
            dx = abs(lp["x"] - s["x"])
            dy = abs(lp["y"] - s["y"])
            if dy < 1e-6:
                continue
            angle = np.degrees(np.arctan2(dy, dx))
            if _MIN_STRUT_ANGLE <= angle <= _MAX_STRUT_ANGLE:
                has_diagonal = True
                break
        if not has_diagonal:
            support_top[si] = _add_node(node_list, s["x"], y_top)

    # ── Build node sets for chords ───────────────────────────────────
    bot_set = set(support_map.values()) | set(load_bot.values())
    top_set = set(load_map.values()) | set(support_top.values())

    bot_sorted = sorted(bot_set, key=lambda i: node_list[i][0])
    top_sorted = sorted(top_set, key=lambda i: node_list[i][0])

    # ── Member construction ──────────────────────────────────────────
    edges = []
    mtypes = []
    edge_set = set()

    def _add_edge(n1, n2, mtype):
        if n1 == n2:
            return
        e = (min(n1, n2), max(n1, n2))
        if e in edge_set:
            return
        dx = node_list[n1][0] - node_list[n2][0]
        dy = node_list[n1][1] - node_list[n2][1]
        if np.hypot(dx, dy) < min_member_length:
            return
        edge_set.add(e)
        edges.append(e)
        mtypes.append(mtype)

    # Bottom chord (tension tie)
    for k in range(len(bot_sorted) - 1):
        _add_edge(bot_sorted[k], bot_sorted[k + 1], "tie")

    # Top chord (compression strut)
    for k in range(len(top_sorted) - 1):
        _add_edge(top_sorted[k], top_sorted[k + 1], "strut")

    # Verticals: each load to its bottom projection
    for li in load_map:
        _add_edge(load_map[li], load_bot[li], "strut")

    # Verticals: each support to its projected top-chord node (if any)
    for si in support_top:
        _add_edge(support_map[si], support_top[si], "strut")

    # Direct diagonal struts: support → load where angle is 25-65 deg
    for si, s in enumerate(supports):
        for li, lp in enumerate(loads):
            dx = abs(lp["x"] - s["x"])
            dy = abs(lp["y"] - s["y"])
            if dy < 1e-6 or dx < 1e-6:
                continue
            angle = np.degrees(np.arctan2(dy, dx))
            if _MIN_STRUT_ANGLE <= angle <= _MAX_STRUT_ANGLE:
                _add_edge(support_map[si], load_map[li], "strut")

    # Panel diagonals: add a BESO-guided diagonal in each panel that
    # does not already have one, ensuring static stability.
    all_xs = sorted(set(node_list[i][0] for i in range(len(node_list))))

    for k in range(len(all_xs) - 1):
        x_left = all_xs[k]
        x_right = all_xs[k + 1]

        bl = [i for i in bot_sorted if abs(node_list[i][0] - x_left) < 0.5]
        br = [i for i in bot_sorted if abs(node_list[i][0] - x_right) < 0.5]
        tl = [i for i in top_sorted if abs(node_list[i][0] - x_left) < 0.5]
        tr = [i for i in top_sorted if abs(node_list[i][0] - x_right) < 0.5]

        if not (bl and br and tl and tr):
            continue

        bl_i, br_i, tl_i, tr_i = bl[0], br[0], tl[0], tr[0]

        diag1 = (min(bl_i, tr_i), max(bl_i, tr_i))
        diag2 = (min(tl_i, br_i), max(tl_i, br_i))

        if diag1 in edge_set or diag2 in edge_set:
            continue

        d1 = _sample_strut_density(node_list[bl_i], node_list[tr_i], class_grid, x_unique, y_unique)
        d2 = _sample_strut_density(node_list[tl_i], node_list[br_i], class_grid, x_unique, y_unique)

        if max(d1, d2) < _MIN_PANEL_DIAG_DENSITY:
            continue

        if d1 >= d2:
            _add_edge(bl_i, tr_i, "strut")
        else:
            _add_edge(tl_i, br_i, "strut")

    if not edges:
        return _fallback_truss(supports, loads)

    # ── Compact node indices ─────────────────────────────────────────
    used = set()
    for i, j in edges:
        used.add(i)
        used.add(j)
    for idx in support_map.values():
        used.add(idx)
    for idx in load_map.values():
        used.add(idx)

    old_to_new = {}
    new_nodes = []
    for old_idx in sorted(used):
        old_to_new[old_idx] = len(new_nodes)
        new_nodes.append(node_list[old_idx])

    new_edges = [(old_to_new[i], old_to_new[j]) for i, j in edges]
    new_support_map = {k: old_to_new[v] for k, v in support_map.items() if v in old_to_new}
    new_load_map = {k: old_to_new[v] for k, v in load_map.items() if v in old_to_new}

    nodes_arr = np.array(new_nodes)
    members_arr = np.array(new_edges, dtype=int) if new_edges else np.zeros((0, 2), dtype=int)

    # ── Classify members and estimate widths ─────────────────────────
    final_types = []
    member_widths = []
    for mid, (i, j) in enumerate(new_edges):
        initial_type = mtypes[mid]
        if initial_type == "tie":
            final_types.append("tie")
        else:
            beso_type = _classify_member(nodes_arr[i], nodes_arr[j], class_grid, x_unique, y_unique)
            final_types.append(beso_type)

        w = _estimate_member_width(nodes_arr[i], nodes_arr[j], active_grid, x_unique, y_unique)
        member_widths.append(w)

    return TrussModel(
        nodes=nodes_arr,
        members=members_arr,
        member_types=final_types,
        support_node_ids=new_support_map,
        load_node_ids=new_load_map,
        member_widths=np.array(member_widths),
    )


def _fallback_truss(supports, loads):
    """Create a minimal truss directly connecting supports to loads when extraction fails."""
    all_points = []
    support_map = {}
    load_map = {}

    for si, s in enumerate(supports):
        support_map[si] = len(all_points)
        all_points.append([s["x"], s["y"]])

    for li, lp in enumerate(loads):
        load_map[li] = len(all_points)
        all_points.append([lp["x"], lp["y"]])

    nodes = np.array(all_points)
    edges = []
    member_types = []

    # Connect each load to each support
    for li in load_map:
        for si in support_map:
            edges.append((support_map[si], load_map[li]))
            member_types.append("strut")

    # Connect supports with a bottom tie
    support_indices = sorted(support_map.values())
    for k in range(len(support_indices) - 1):
        edges.append((support_indices[k], support_indices[k + 1]))
        member_types.append("tie")

    members = np.array(edges, dtype=int) if edges else np.zeros((0, 2), dtype=int)

    return TrussModel(
        nodes=nodes,
        members=members,
        member_types=member_types,
        support_node_ids=support_map,
        load_node_ids=load_map,
        member_widths=np.ones(len(edges)) * 5.0,
    )
