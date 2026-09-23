"""Adaptive mesh generation for Q4 plane-stress FEM."""

import numpy as np


def generate_adaptive_mesh(L, h, supports, loads, max_edge, max_AR):
    """
    Generate a structured Q4 mesh with forced grid lines at supports and loads.

    Returns
    -------
    nodes            : (n_nodes, 2) array of [x, y] coordinates (in)
    elems            : (n_elems, 4) node index array (CCW: BL, BR, TR, TL)
    support_node_ids : {i: node_id} for each support in input list
    load_node_ids    : {i: node_id} for each load in input list
    """
    TOL = 1e-6

    # Step 1: Collect forced grid lines
    x_forced = sorted(set(
        [0.0, L] + [s['x'] for s in supports] + [lp['x'] for lp in loads]))
    y_forced = sorted(set(
        [0.0, h] + [s['y'] for s in supports] + [lp['y'] for lp in loads]))

    def dedup(lst):
        out = [lst[0]]
        for v in lst[1:]:
            if abs(v - out[-1]) > TOL:
                out.append(v)
        return out

    x_forced = dedup(x_forced)
    y_forced = dedup(y_forced)

    # Step 2: Subdivide intervals to satisfy max_edge and max_AR
    def subdivide_intervals(forced_x, forced_y, max_edge, max_AR, n_pass=3):
        x_lines = list(forced_x)
        y_lines = list(forced_y)

        for _ in range(n_pass):
            # Subdivide x-intervals
            new_x = [x_lines[0]]
            for i in range(len(x_lines) - 1):
                dx = x_lines[i+1] - x_lines[i]
                nx = max(1, int(np.ceil(dx / max_edge)))
                if len(y_lines) > 1:
                    min_dy = min(y_lines[j+1] - y_lines[j]
                                 for j in range(len(y_lines)-1))
                    nx = max(nx, int(np.ceil(dx / (max_AR * min_dy))))
                for k in range(1, nx + 1):
                    new_x.append(x_lines[i] + k * dx / nx)
            x_lines = sorted(set(np.round(new_x, 10)))

            # Subdivide y-intervals
            new_y = [y_lines[0]]
            for j in range(len(y_lines) - 1):
                dy = y_lines[j+1] - y_lines[j]
                ny = max(1, int(np.ceil(dy / max_edge)))
                if len(x_lines) > 1:
                    min_dx = min(x_lines[i+1] - x_lines[i]
                                 for i in range(len(x_lines)-1))
                    ny = max(ny, int(np.ceil(dy / (max_AR * min_dx))))
                for k in range(1, ny + 1):
                    new_y.append(y_lines[j] + k * dy / ny)
            y_lines = sorted(set(np.round(new_y, 10)))

        return np.array(x_lines), np.array(y_lines)

    x_lines, y_lines = subdivide_intervals(x_forced, y_forced, max_edge, max_AR)
    nx_lines = len(x_lines)
    ny_lines = len(y_lines)

    # Step 3: Build node array
    # node_id = ix * ny_lines + iy
    n_nodes = nx_lines * ny_lines
    nodes = np.zeros((n_nodes, 2))
    for ix, xv in enumerate(x_lines):
        for iy, yv in enumerate(y_lines):
            nid = ix * ny_lines + iy
            nodes[nid, 0] = xv
            nodes[nid, 1] = yv

    # Step 4: Build element connectivity (CCW: BL, BR, TR, TL)
    n_elems = (nx_lines - 1) * (ny_lines - 1)
    elems = np.zeros((n_elems, 4), dtype=int)
    eid = 0
    for ix in range(nx_lines - 1):
        for iy in range(ny_lines - 1):
            bl = ix * ny_lines + iy
            br = (ix + 1) * ny_lines + iy
            tr = (ix + 1) * ny_lines + (iy + 1)
            tl = ix * ny_lines + (iy + 1)
            elems[eid] = [bl, br, tr, tl]
            eid += 1

    # Step 5: Identify support and load nodes
    def find_nearest_node(x, y, nodes):
        dist = np.hypot(nodes[:, 0] - x, nodes[:, 1] - y)
        nid = int(np.argmin(dist))
        assert dist[nid] < 1e-4, (
            f"Nearest node to ({x}, {y}) is {dist[nid]:.4f} in away – "
            f"mesh did not place a node at this coordinate")
        return nid

    support_node_ids = {i: find_nearest_node(s['x'], s['y'], nodes)
                        for i, s in enumerate(supports)}
    load_node_ids = {i: find_nearest_node(lp['x'], lp['y'], nodes)
                     for i, lp in enumerate(loads)}

    return nodes, elems, support_node_ids, load_node_ids


def element_dimensions(nodes, elems):
    """Return (widths, heights) arrays for each Q4 element."""
    BL = nodes[elems[:, 0]]
    BR = nodes[elems[:, 1]]
    TL = nodes[elems[:, 3]]
    widths = np.linalg.norm(BR - BL, axis=1)
    heights = np.linalg.norm(TL - BL, axis=1)
    return widths, heights


def element_centroids(nodes, elems):
    """Centroid (cx, cy) arrays for all elements."""
    cx = nodes[elems, 0].mean(axis=1)
    cy = nodes[elems, 1].mean(axis=1)
    return cx, cy
