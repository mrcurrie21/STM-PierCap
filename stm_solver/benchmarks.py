"""Source-traceable regression benchmarks for STM generation procedures."""

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from .design_checks import (
    REBAR_TABLE,
    calculate_standard_hook_development,
    check_nodal_face_capacity,
    check_tie,
    extended_nodal_zone_anchorage_length,
    projected_strut_interface_width,
    required_reinforced_strut_steel_area,
)
from .ground_structure import (
    GroundStructureResult,
    generate_frame_boundary_candidates,
    optimize_frame_boundary,
    optimize_frame_boundary_actions,
    optimize_ground_structure,
    optimize_pier_cap,
)


@dataclass
class BenchmarkOutcome:
    """Comparison between one generated STM and its published reference values."""

    case_id: str
    passed: bool
    checks: dict
    result: GroundStructureResult


@dataclass
class DesignBenchmarkOutcome:
    """Published design-detail values compared with isolated calculations."""

    case_id: str
    passed: bool
    checks: dict
    calculated: dict


def load_benchmark_suite(path):
    """Load a benchmark TOML file without discarding source metadata."""
    with open(Path(path), "rb") as stream:
        suite = tomllib.load(stream)
    if "suite_id" not in suite or "cases" not in suite:
        raise ValueError("Benchmark suite requires suite_id and cases")
    return suite


def active_cases(suite):
    """Return benchmark cases implemented by the current solver."""
    return [case for case in suite["cases"] if case.get("status") == "active"]


def run_hand_multi_panel_benchmark(load=100.0):
    """Solve a determinate symmetric two-panel truss with hand-known forces.

    Each top node carries ``load`` downward. Reactions are ``load`` at each end,
    outer 45-degree diagonals carry ``sqrt(2)*load`` compression, the top chord
    carries ``load`` compression, bottom chords carry ``load`` tension, and the
    two center diagonals are zero-force members.
    """
    load = float(load)
    if not np.isfinite(load) or load <= 0.0:
        raise ValueError("benchmark load must be positive and finite")
    nodes = np.array([
        [0.0, 0.0], [10.0, 0.0], [20.0, 0.0],
        [5.0, 5.0], [15.0, 5.0],
    ])
    members = np.array([
        [0, 1], [1, 2], [3, 4],
        [0, 3], [3, 1], [1, 4], [4, 2],
    ])
    result = optimize_ground_structure(
        nodes, members, {3: (0.0, -load), 4: (0.0, -load)},
        constrained_dofs=[0, 1, 5], force_tolerance=1e-10,
    )
    expected = np.array([
        load, load, -load,
        -np.sqrt(2.0) * load, 0.0, 0.0, -np.sqrt(2.0) * load,
    ])
    checks = {
        "member_forces": bool(np.allclose(
            result.candidate_forces, expected, atol=1e-7, rtol=0.0,
        )),
        "left_vertical_reaction": bool(np.isclose(
            result.reactions[1], load, atol=1e-7, rtol=0.0,
        )),
        "right_vertical_reaction": bool(np.isclose(
            result.reactions[5], load, atol=1e-7, rtol=0.0,
        )),
        "horizontal_reaction": bool(np.isclose(
            result.reactions[0], 0.0, atol=1e-7, rtol=0.0,
        )),
        "equilibrium": result.equilibrium_residual < 1e-9,
    }
    return BenchmarkOutcome(
        case_id="hand_symmetric_two_panel",
        passed=all(checks.values()), checks=checks, result=result,
    )


def run_fhwa_design_benchmark(case):
    """Compare design calculations with published FHWA Example 1 values."""
    reference = case.get("design_reference")
    if reference is None:
        raise ValueError("Benchmark case has no published design reference")
    fy = float(reference["fy_ksi"])
    fc_prime = float(reference["fc_ksi"])
    phi = float(reference["phi_tie"])
    bottom_tie = check_tie(
        -1, reference["bottom_tie_force"], fy, phi=phi,
        preferred_bar_size=int(reference["bottom_tie_bar_size"]),
    )
    vertical_tie = check_tie(-1, reference["vertical_tie_force"], fy, phi=phi)
    provided_area = (
        int(reference["bottom_tie_bar_count"])
        * REBAR_TABLE[int(reference["bottom_tie_bar_size"])]["Ab"]
    )
    factored_capacity = phi * fy * provided_area
    cct_width = projected_strut_interface_width(
        reference["cct_bearing_width"], reference["cct_back_face_depth"],
        reference["strut_angle_degrees"],
    )
    ccc_width = projected_strut_interface_width(
        reference["ccc_final_bearing_width"], reference["ccc_back_face_depth"],
        reference["strut_angle_degrees"],
    )
    hook = calculate_standard_hook_development(
        int(reference["bottom_tie_bar_size"]), fy, fc_prime,
        apply_excess_reinforcement_factor=True,
        as_required=bottom_tie.As_required, as_provided=provided_area,
    )
    hook_available = extended_nodal_zone_anchorage_length(
        reference["ccc_final_bearing_width"], reference["cct_back_face_depth"],
        reference["strut_angle_degrees"], reference["hook_end_overhang"],
        reference["hook_clear_cover"],
    )
    face_definitions = {
        "cct_bearing": "bearing",
        "cct_strut": "strut_interface",
        "ccc_bearing": "bearing",
        "ccc_back": "back",
        "ccc_initial_strut": "strut_interface",
        "ccc_final_strut": "strut_interface",
    }
    face_checks = {}
    member_width = float(reference["member_width"])
    for prefix, face_type in face_definitions.items():
        face_checks[prefix] = check_nodal_face_capacity(
            reference[f"{prefix}_demand"],
            reference[f"{prefix}_area"] / member_width,
            member_width, fc_prime, reference[f"{prefix}_factor"],
            phi=reference["phi_compression"], face_type=face_type,
            zone_type="CCT" if prefix.startswith("cct") else "CCC",
            group_label="FHWA Example 1",
        )
    top_strut_steel_required = required_reinforced_strut_steel_area(
        reference["ccc_back_demand"], reference["ccc_back_capacity"], fy,
        phi=reference["phi_compression"],
    )
    top_strut_steel_provided = (
        int(reference["top_strut_steel_bar_count"])
        * REBAR_TABLE[int(reference["top_strut_steel_bar_size"])]["Ab"]
    )
    calculated = {
        "bottom_tie_required_area": bottom_tie.As_required,
        "bottom_tie_factored_capacity": factored_capacity,
        "vertical_tie_required_area": vertical_tie.As_required,
        "cct_interface_width": cct_width,
        "ccc_final_interface_width": ccc_width,
        "hook_basic_length": hook.basic_length,
        "hook_required_length": hook.required_length,
        "hook_available_length": hook_available,
        "top_strut_steel_required": top_strut_steel_required,
        "top_strut_steel_provided": top_strut_steel_provided,
    }
    for prefix, face_check in face_checks.items():
        calculated[f"{prefix}_capacity"] = face_check.capacity
        calculated[f"{prefix}_dc"] = face_check.dc_ratio
    tolerances = {
        "bottom_tie_required_area": 0.01,
        "bottom_tie_factored_capacity": 1.0,
        "vertical_tie_required_area": 0.01,
        "cct_interface_width": 0.1,
        "ccc_final_interface_width": 0.1,
        "hook_basic_length": 0.1,
        "hook_required_length": 0.1,
        "hook_available_length": 0.1,
        "top_strut_steel_required": 0.01,
        "top_strut_steel_provided": 0.01,
    }
    for prefix in face_definitions:
        tolerances[f"{prefix}_capacity"] = 1.0
        # Source D/C values are derived from displayed whole-kip capacities.
        tolerances[f"{prefix}_dc"] = 0.002
    checks = {
        name: bool(np.isclose(value, reference[name], atol=tolerances[name], rtol=0.0))
        for name, value in calculated.items()
    }
    checks.update({
        "cct_faces_pass": all(
            face_checks[name].status == "OK"
            for name in ("cct_bearing", "cct_strut")
        ),
        "ccc_initial_back_face_fails": face_checks["ccc_back"].status == "NG",
        "ccc_initial_strut_face_fails": (
            face_checks["ccc_initial_strut"].status == "NG"
        ),
        "ccc_final_strut_face_passes": (
            face_checks["ccc_final_strut"].status == "OK"
        ),
        "top_strut_reinforcement_passes": (
            top_strut_steel_provided >= top_strut_steel_required
        ),
    })
    checks["hook_anchorage_passes"] = (
        hook_available >= float(reference["hook_rounded_length"])
    )
    return DesignBenchmarkOutcome(
        case_id=case["id"], passed=all(checks.values()),
        checks=checks, calculated=calculated,
    )


def generate_frame_candidate_benchmark(case):
    """Optimize candidates assembled from a prescribed frame benchmark's nodes."""
    node_ids = {node["id"]: index for index, node in enumerate(case["nodes"])}
    top_nodes = [node for node in case["nodes"] if node["role"] == "top"]
    lower_nodes = [node for node in case["nodes"] if node["role"] == "lower"]
    boundary_nodes = []
    for boundary in case["boundaries"]:
        node = case["nodes"][node_ids[boundary["node"]]]
        boundary_nodes.append({
            "x": node["x"],
            "y": node["y"],
            "connect_group": boundary["connect_group"],
            "connect_index": boundary["connect_index"],
            "additional_connections": boundary.get("additional_connections", []),
            "connect_boundary_indices": boundary.get("connect_boundary_indices", []),
        })
    nodes, members, boundary_map = generate_frame_boundary_candidates(
        top_nodes,
        lower_nodes,
        boundary_nodes,
        min_angle=case.get("generation_min_angle", 25.0),
        max_angle=case.get("generation_max_angle", 90.0),
    )
    nodal_loads = {
        node_ids[load["node"]]: (load.get("Px", 0.0), load.get("Py", 0.0))
        for load in case["nodal_loads"]
    }
    constrained_dofs = [
        2 * boundary_map[index] + (0 if dof == "x" else 1)
        for index, boundary in enumerate(case["boundaries"])
        for dof in boundary["dofs"]
    ]
    candidate_lookup = {
        tuple(sorted(member)): index for index, member in enumerate(members.tolist())
    }
    relative_tolerance = float(case.get("fixed_force_relative_tolerance", 0.0))
    member_force_bounds = {}
    if case.get("generation_diagonal_webs_compression_only", False):
        n_top = len(top_nodes)
        n_lower = len(lower_nodes)
        for candidate_index, (i, j) in enumerate(members):
            is_top_lower_web = (
                (i < n_top and n_top <= j < n_top + n_lower)
                or (j < n_top and n_top <= i < n_top + n_lower)
            )
            if is_top_lower_web and not np.isclose(nodes[i, 0], nodes[j, 0]):
                member_force_bounds[candidate_index] = (-np.inf, 0.0)
    for published in case["members"]:
        if not published.get("fix_expected_force", False):
            continue
        pair = tuple(sorted((node_ids[published["i"]], node_ids[published["j"]])))
        candidate_index = candidate_lookup[pair]
        force = float(published["expected_force"])
        delta = relative_tolerance * max(abs(force), 1.0)
        member_force_bounds[candidate_index] = (force - delta, force + delta)
    return optimize_ground_structure(
        nodes,
        members,
        nodal_loads,
        constrained_dofs,
        force_tolerance=case.get("generation_force_tolerance", 1e-3),
        member_force_bounds=member_force_bounds,
    )


def run_pier_cap_benchmark(case):
    """Run an active 2D benchmark and compare its source-defined invariants."""
    if case.get("status") != "active":
        raise ValueError(f"Benchmark {case.get('id', '<unknown>')} is not active")

    result = optimize_pier_cap(
        case["loads"],
        case["piles"],
        top_tie_y=case.get("top_tie_y"),
        bottom_tie_y=case.get("bottom_tie_y"),
        min_angle=case.get("min_angle", 20.0),
        max_angle=case.get("max_angle", 75.0),
    )
    tolerance = float(case.get("force_tolerance", 1e-3))
    checks = {
        "equilibrium": result.equilibrium_residual <= 1e-7,
    }

    expected_reactions = case.get("expected_vertical_reactions")
    if expected_reactions is not None:
        actual_reactions = []
        for pile_index in range(len(case["piles"])):
            node = result.truss_model.support_node_ids[pile_index]
            actual_reactions.append(result.reactions.get(2 * node + 1, 0.0))
        checks["vertical_reactions"] = np.allclose(
            actual_reactions, expected_reactions, atol=tolerance, rtol=0.0
        )

    expected_diagonal = case.get("expected_diagonal_compression")
    if expected_diagonal is not None:
        diagonal_compression = []
        for (i, j), force in zip(result.truss_model.members, result.member_forces):
            delta = result.truss_model.nodes[j] - result.truss_model.nodes[i]
            if abs(delta[0]) > 1e-8 and abs(delta[1]) > 1e-8 and force < 0:
                diagonal_compression.append(abs(force))
        checks["diagonal_compression"] = (
            len(diagonal_compression) == 2
            and np.allclose(diagonal_compression, expected_diagonal, atol=tolerance, rtol=0.0)
        )

    expected_chord = case.get("expected_chord_force")
    if expected_chord is not None:
        horizontal = []
        for (i, j), force in zip(result.truss_model.members, result.member_forces):
            delta = result.truss_model.nodes[j] - result.truss_model.nodes[i]
            if abs(delta[1]) <= 1e-8:
                horizontal.append(abs(force))
        checks["chord_forces"] = bool(horizontal) and np.allclose(
            horizontal, expected_chord, atol=tolerance, rtol=0.0
        )

    return BenchmarkOutcome(
        case_id=case["id"],
        passed=all(bool(value) for value in checks.values()),
        checks=checks,
        result=result,
    )


def run_prescribed_benchmark(case):
    """Solve a published topology and compare its member-force vector."""
    if case.get("status") != "active":
        raise ValueError(f"Benchmark {case.get('id', '<unknown>')} is not active")
    if case.get("benchmark_type") != "prescribed_ground_structure":
        raise ValueError("Case is not a prescribed-ground-structure benchmark")

    node_ids = {node["id"]: index for index, node in enumerate(case["nodes"])}
    nodes = np.array([[node["x"], node["y"]] for node in case["nodes"]], dtype=float)
    members = np.array(
        [[node_ids[member["i"]], node_ids[member["j"]]] for member in case["members"]],
        dtype=int,
    )
    nodal_loads = {
        node_ids[load["node"]]: (load.get("Px", 0.0), load.get("Py", 0.0))
        for load in case["nodal_loads"]
    }
    dof_offset = {"x": 0, "y": 1}
    constrained_dofs = [
        2 * node_ids[boundary["node"]] + dof_offset[dof]
        for boundary in case["boundaries"]
        for dof in boundary["dofs"]
    ]
    fixed_members = [
        (index, member["expected_force"])
        for index, member in enumerate(case["members"])
        if member.get("fix_expected_force", False)
    ]
    member_force_equalities = None
    member_force_bounds = None
    if fixed_members:
        tolerance = float(case.get("fixed_force_relative_tolerance", 0.0))
        if tolerance:
            member_force_bounds = {
                index: (
                    force - tolerance * max(abs(force), 1.0),
                    force + tolerance * max(abs(force), 1.0),
                )
                for index, force in fixed_members
            }
        else:
            matrix = np.zeros((len(fixed_members), len(members)))
            rhs = np.zeros(len(fixed_members))
            for row, (member_index, force) in enumerate(fixed_members):
                matrix[row, member_index] = 1.0
                rhs[row] = force
            member_force_equalities = (matrix, rhs)
    result = optimize_ground_structure(
        nodes,
        members,
        nodal_loads,
        constrained_dofs,
        # Preserve zero-force candidates so the returned vector stays aligned
        # with the published topology during benchmark comparison.
        force_tolerance=-1.0,
        member_force_equalities=member_force_equalities,
        member_force_bounds=member_force_bounds,
    )
    expected = np.array([member["expected_force"] for member in case["members"]])
    actual = result.member_forces
    relative_error = np.abs(actual - expected) / np.maximum(np.abs(expected), 1.0)
    tolerance = float(case["relative_force_tolerance"])
    checks = {
        "equilibrium": result.equilibrium_residual <= 1e-7,
        "force_sense": np.array_equal(np.sign(actual), np.sign(expected)),
        "published_member_forces": bool(np.max(relative_error) <= tolerance),
    }
    if fixed_members:
        tolerance = float(case.get("fixed_force_relative_tolerance", 0.0))
        checks["fixed_interface_forces"] = all(
            abs(actual[index] - force) <= tolerance * max(abs(force), 1.0) + 1e-7
            for index, force in fixed_members
        )
    if case.get("check_candidate_generation", False):
        generated = generate_frame_candidate_benchmark(case)
        expected_members = {tuple(sorted(member)) for member in members.tolist()}
        generated_members = {
            tuple(sorted(member)) for member in generated.truss_model.members.tolist()
        }
        overlap = expected_members & generated_members
        recall = len(overlap) / len(expected_members)
        precision = len(overlap) / len(generated_members)
        checks["candidate_generation_equilibrium"] = (
            generated.equilibrium_residual <= 1e-7
        )
        checks["candidate_topology_recall"] = recall >= float(
            case.get("minimum_topology_recall", 1.0)
        )
        checks["candidate_topology_precision"] = precision >= float(
            case.get("minimum_topology_precision", 1.0)
        )
    if case.get("check_frame_generation", False):
        top_nodes = [
            (node["x"], node["y"]) for node in case["nodes"] if node["role"] == "top"
        ]
        lower_nodes = [
            {
                "x": node["x"],
                "y": node["y"],
                "connect_top_indices": node.get("connect_top_indices"),
            }
            for node in case["nodes"] if node["role"] == "lower"
        ]
        boundary_nodes = []
        boundary_forces = []
        for boundary_item in case["boundaries"]:
            nid = node_ids[boundary_item["node"]]
            boundary_nodes.append({
                "x": nodes[nid, 0],
                "y": nodes[nid, 1],
                "connect_group": boundary_item["connect_group"],
                "connect_index": boundary_item["connect_index"],
            })
            boundary_forces.append((
                result.reactions.get(2 * nid, 0.0),
                result.reactions.get(2 * nid + 1, 0.0),
            ))
        top_ids = [node_ids[node["id"]] for node in case["nodes"] if node["role"] == "top"]
        loads_by_node = {
            node_ids[load["node"]]: (load.get("Px", 0.0), load.get("Py", 0.0))
            for load in case["nodal_loads"]
        }
        top_loads = [loads_by_node.get(nid, (0.0, 0.0)) for nid in top_ids]
        generated = optimize_frame_boundary(
            top_nodes,
            lower_nodes,
            boundary_nodes,
            top_loads,
            boundary_forces,
            min_angle=25.0,
            force_tolerance=1e-3,
        )
        expected_members = {tuple(sorted(member)) for member in members.tolist()}
        generated_members = {
            tuple(sorted(member)) for member in generated.truss_model.members.tolist()
        }
        checks["frame_candidate_topology"] = generated_members == expected_members
        axial = -sum(force[1] for force in top_loads)
        moment = -sum(
            top_nodes[index][0] * force[1] - top_nodes[index][1] * force[0]
            for index, force in enumerate(top_loads)
        )
        action_generated = optimize_frame_boundary_actions(
            top_nodes,
            lower_nodes,
            boundary_nodes,
            top_loads,
            axial_compression=axial,
            moment_about_reference=moment,
            min_angle=25.0,
            force_tolerance=1e-3,
        )
        action_members = {
            tuple(sorted(member)) for member in action_generated.truss_model.members.tolist()
        }
        checks["section_action_topology"] = action_members == expected_members
    return BenchmarkOutcome(
        case_id=case["id"],
        passed=all(bool(value) for value in checks.values()),
        checks=checks,
        result=result,
    )


def run_benchmark(case):
    """Dispatch a benchmark case to its declared comparison procedure."""
    benchmark_type = case.get("benchmark_type")
    if benchmark_type == "pier_cap_generation":
        return run_pier_cap_benchmark(case)
    if benchmark_type == "prescribed_ground_structure":
        return run_prescribed_benchmark(case)
    raise ValueError(f"Unsupported benchmark type: {benchmark_type!r}")
