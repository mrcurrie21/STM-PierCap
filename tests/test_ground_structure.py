"""Tests for discrete pier-cap ground-structure optimization."""

import numpy as np
import pytest

from stm_solver.ground_structure import (
    build_pier_cap_external_faces,
    find_member_crossings,
    generate_frame_boundary_candidates,
    generate_pier_cap_candidates,
    locate_linear_frame_boundary,
    optimize_frame_boundary,
    optimize_frame_boundary_actions,
    optimize_ground_structure,
    optimize_pier_cap,
    optimize_pier_cap_load_cases,
)


def test_triangle_selects_two_struts_and_bottom_tie():
    nodes = np.array([[0.0, 0.0], [10.0, 0.0], [5.0, 5.0]])
    members = np.array([[0, 1], [0, 2], [1, 2]])

    result = optimize_ground_structure(
        nodes,
        members,
        nodal_loads={2: (0.0, -100.0)},
        constrained_dofs=[0, 1, 3],
    )

    assert result.equilibrium_residual < 1e-8
    assert len(result.member_forces) == 3
    horizontal = next(
        force
        for force, (i, j) in zip(result.member_forces, result.truss_model.members)
        if nodes[i, 1] == nodes[j, 1]
    )
    diagonals = [
        force
        for force, (i, j) in zip(result.member_forces, result.truss_model.members)
        if nodes[i, 1] != nodes[j, 1]
    ]
    assert horizontal > 0.0
    assert all(force < 0.0 for force in diagonals)


def test_candidate_generation_uses_reinforcement_centrelines():
    loads = [{"x": 5.0, "y": 9.0, "Px": 0.0, "Py": -100.0}]
    piles = [
        {"x": 0.0, "y": 0.0, "type": "pin"},
        {"x": 10.0, "y": 0.0, "type": "roller"},
    ]
    nodes, members, load_ids, pile_ids = generate_pier_cap_candidates(
        loads, piles, top_tie_y=8.0, bottom_tie_y=1.0
    )

    assert len(nodes) >= 6
    assert len(members) > 0
    assert nodes[load_ids[0]].tolist() == [5.0, 9.0]
    assert nodes[pile_ids[1]].tolist() == [10.0, 0.0]
    assert any(np.isclose(nodes[:, 1], 8.0))
    assert any(np.isclose(nodes[:, 1], 1.0))


def test_finite_bearing_and_foundation_faces_are_centered_on_resultants():
    loads = [{"x": 5.0, "y": 9.0, "Py": -100.0, "bearing_width": 4.0}]
    piles = [
        {"x": 0.0, "y": 0.0, "type": "pin", "face_width": 3.0},
        {
            "x": 10.0, "y": 0.0, "type": "roller", "diameter": 6.0,
            "foundation_type": "shaft",
        },
    ]
    nodes, _, load_ids, pile_ids = generate_pier_cap_candidates(loads, piles)
    faces = build_pier_cap_external_faces(loads, piles, load_ids, pile_ids)

    assert [(face.kind, face.width) for face in faces] == [
        ("bearing_plate", 4.0), ("pile_head", 3.0), ("shaft_head", 6.0)
    ]
    assert faces[0].center == (5.0, 9.0)
    assert faces[0].start == (3.0, 9.0)
    assert faces[0].end == (7.0, 9.0)
    assert faces[0].node_id == load_ids[0]
    assert faces[0].inward_normal == (0.0, -1.0)
    assert faces[1].inward_normal == (0.0, 1.0)
    assert faces[2].inward_normal == (0.0, 1.0)
    assert nodes[faces[2].node_id].tolist() == [10.0, 0.0]


def test_optimize_pier_cap_attaches_finite_faces():
    loads = [{"x": 5.0, "y": 5.0, "Py": -100.0, "face_width": 4.0}]
    piles = [
        {"x": 0.0, "y": 0.0, "type": "pin", "diameter": 2.0},
        {"x": 10.0, "y": 0.0, "type": "roller", "diameter": 2.0},
    ]
    result = optimize_pier_cap(loads, piles, min_angle=20.0, max_angle=70.0)

    assert len(result.truss_model.external_faces) == 3


@pytest.mark.parametrize("width", [0.0, -1.0, np.inf])
def test_external_faces_reject_invalid_width(width):
    loads = [{"x": 5.0, "y": 5.0, "Py": -100.0, "face_width": width}]
    piles = [{"x": 0.0, "y": 0.0, "type": "pin"}]
    _, _, load_ids, pile_ids = generate_pier_cap_candidates(loads, piles)

    with pytest.raises(ValueError, match="positive finite"):
        build_pier_cap_external_faces(loads, piles, load_ids, pile_ids)


def test_symmetric_pier_cap_balances_vertical_reactions():
    loads = [{"x": 5.0, "y": 5.0, "Px": 0.0, "Py": -100.0}]
    piles = [
        {"x": 0.0, "y": 0.0, "type": "pin"},
        {"x": 10.0, "y": 0.0, "type": "roller"},
    ]
    result = optimize_pier_cap(loads, piles, min_angle=20.0, max_angle=70.0)

    assert result.equilibrium_residual < 1e-8
    left_node = result.truss_model.support_node_ids[0]
    right_node = result.truss_model.support_node_ids[1]
    assert result.reactions[2 * left_node + 1] == pytest.approx(50.0)
    assert result.reactions[2 * right_node + 1] == pytest.approx(50.0)
    assert any(kind == "tie" for kind in result.truss_model.member_types)
    assert any(kind == "strut" for kind in result.truss_model.member_types)


def test_multiple_cases_share_one_pruned_candidate_structure():
    load_cases = {
        "left": [
            {"id": "B1", "x": 3.0, "y": 8.0, "Py": -80.0, "face_width": 2.0},
            {"id": "B2", "x": 7.0, "y": 8.0, "Py": -20.0, "face_width": 2.0},
        ],
        "right": [
            {"id": "B1", "x": 3.0, "y": 8.0, "Py": -20.0, "face_width": 2.0},
            {"id": "B2", "x": 7.0, "y": 8.0, "Py": -80.0, "face_width": 2.0},
        ],
    }
    piles = [
        {"id": "P1", "x": 0.0, "y": 0.0, "type": "pin", "face_width": 2.0},
        {"id": "P2", "x": 10.0, "y": 0.0, "type": "roller", "face_width": 2.0},
    ]
    result = optimize_pier_cap_load_cases(
        load_cases, piles, top_tie_y=7.0, bottom_tie_y=1.0,
        min_angle=20.0, max_angle=75.0,
    )

    assert result.initial_candidate_count > len(result.members)
    assert len(result.common_candidate_ids) == len(result.members)
    assert result.pruning_iterations >= 1
    assert set(result.case_results) == {"left", "right"}
    assert all(
        len(case.candidate_forces) == len(result.members)
        for case in result.case_results.values()
    )
    assert all(
        case.equilibrium_residual < 1e-8
        for case in result.case_results.values()
    )
    assert any(record.rejection_reason for record in result.candidate_records)


def test_multiple_cases_require_identical_physical_load_locations():
    load_cases = {
        "one": [{"id": "B1", "x": 3.0, "y": 8.0, "Py": -10.0}],
        "two": [{"id": "B1", "x": 4.0, "y": 8.0, "Py": -10.0}],
    }
    piles = [{"id": "P1", "x": 0.0, "y": 0.0, "type": "pin"}]
    with pytest.raises(ValueError, match="common load locations"):
        optimize_pier_cap_load_cases(load_cases, piles)


def test_inset_reinforcement_centrelines_remain_connected():
    loads = [{"x": 5.0, "y": 6.0, "Px": 0.0, "Py": -100.0}]
    piles = [
        {"x": 0.0, "y": 0.0, "type": "pin"},
        {"x": 10.0, "y": 0.0, "type": "roller"},
    ]
    result = optimize_pier_cap(
        loads,
        piles,
        top_tie_y=5.5,
        bottom_tie_y=0.5,
        min_angle=20.0,
        max_angle=70.0,
    )

    assert result.equilibrium_residual < 1e-8
    assert sum(result.reactions.values()) == pytest.approx(100.0)


def test_non_nodal_member_crossings_are_detected():
    nodes = np.array([
        [0.0, 0.0], [10.0, 10.0], [0.0, 10.0], [10.0, 0.0], [20.0, 10.0]
    ])
    members = np.array([[0, 1], [2, 3], [1, 4]])

    assert find_member_crossings(nodes, members) == [(0, 1)]


def test_pier_cap_diagonal_webs_default_to_compression_without_crossings():
    loads = [
        {"x": 6.5, "y": 30.0, "Py": -42.975},
        {"x": 57.5, "y": 30.0, "Py": -98.838},
        {"x": 72.0, "y": 30.0, "Py": -121.776},
        {"x": 120.0, "y": 30.0, "Py": -121.776},
        {"x": 134.5, "y": 30.0, "Py": -98.838},
        {"x": 185.5, "y": 30.0, "Py": -42.975},
    ]
    piles = [
        {"x": 36.0, "y": 0.0, "type": "pin"},
        {"x": 96.0, "y": 0.0, "type": "roller"},
        {"x": 156.0, "y": 0.0, "type": "pin"},
    ]
    result = optimize_pier_cap(
        loads, piles, top_tie_y=27.0, bottom_tie_y=3.0,
        min_angle=25.0, max_angle=75.0,
    )

    for (i, j), force in zip(result.truss_model.members, result.member_forces):
        delta = result.truss_model.nodes[j] - result.truss_model.nodes[i]
        crosses_layers = not np.isclose(delta[0], 0.0) and not np.isclose(delta[1], 0.0)
        if crosses_layers:
            assert force < 0.0
    assert find_member_crossings(
        result.truss_model.nodes, result.truss_model.members
    ) == []


def test_inadmissible_ground_structure_has_clear_error():
    nodes = np.array([[0.0, 0.0], [0.0, 5.0]])
    members = np.array([[0, 1]])
    with pytest.raises(ValueError, match="No admissible"):
        optimize_ground_structure(
            nodes,
            members,
            nodal_loads={1: (10.0, -10.0)},
            constrained_dofs=[0, 1],
        )


def test_member_force_bounds_are_enforced():
    nodes = np.array([[0.0, 0.0], [0.0, 5.0]])
    members = np.array([[0, 1]])
    result = optimize_ground_structure(
        nodes,
        members,
        nodal_loads={1: (0.0, -10.0)},
        constrained_dofs=[0, 1],
        member_force_bounds={0: (-10.1, -9.9)},
    )
    assert result.member_forces[0] == pytest.approx(-10.0)

    with pytest.raises(ValueError, match="No admissible"):
        optimize_ground_structure(
            nodes,
            members,
            nodal_loads={1: (0.0, -10.0)},
            constrained_dofs=[0, 1],
            member_force_bounds={0: (-9.0, -8.0)},
        )


def _fhwa_cantilever_frame_data():
    top = [(0.67, 8.465), (6.97, 8.140), (22.99, 7.314)]
    lower = [(7.52, -0.198), (9.69, -0.310)]
    boundary = [
        {"x": 0.67, "y": -4.0, "connect_group": "top", "connect_index": 0},
        {"x": 7.52, "y": -4.0, "connect_group": "lower", "connect_index": 0},
        {"x": 9.69, "y": -4.0, "connect_group": "lower", "connect_index": 1},
    ]
    return top, lower, boundary


def test_frame_boundary_candidates_include_chords_web_and_resultant_branches():
    top, lower, boundary = _fhwa_cantilever_frame_data()
    nodes, members, boundary_map = generate_frame_boundary_candidates(
        top, lower, boundary, min_angle=25.0
    )

    member_set = {tuple(member) for member in members}
    assert len(nodes) == 8
    assert (0, 1) in member_set  # top chord AB
    assert (3, 4) in member_set  # lower chord DE
    assert (0, 3) in member_set  # direct frame-corner strut AD
    assert (0, boundary_map[0]) in member_set  # boundary tie branch AA'
    assert (3, boundary_map[1]) in member_set  # compression branch DD'


def test_frame_boundary_candidates_support_moment_frame_corner_fans():
    top = [(0.0, 5.0), (10.0, 5.0)]
    lower = [(3.0, 0.0), (7.0, 0.0)]
    boundary = [
        {
            "x": 0.0,
            "y": -5.0,
            "connect_group": "top",
            "connect_index": 0,
            "additional_connections": [
                {"connect_group": "lower", "connect_index": 0}
            ],
            "connect_boundary_indices": [1],
        },
        {"x": 3.0, "y": -5.0, "connect_group": "lower", "connect_index": 0},
    ]
    _, members, boundary_map = generate_frame_boundary_candidates(
        top, lower, boundary, min_angle=25.0
    )

    member_set = {tuple(member) for member in members}
    assert (0, boundary_map[0]) in member_set
    assert (2, boundary_map[0]) in member_set
    assert (boundary_map[0], boundary_map[1]) in member_set


def test_frame_boundary_generator_recovers_fhwa_direct_panel_topology():
    top, lower, boundary = _fhwa_cantilever_frame_data()
    result = optimize_frame_boundary(
        top,
        lower,
        boundary,
        top_loads=[(0.0, 0.0), (0.0, -2005.0), (0.0, -926.0)],
        boundary_forces=[
            (0.0, -1636.917025227115),
            (0.0, 3641.839432050037),
            (0.0, 926.0775931770786),
        ],
        min_angle=25.0,
        force_tolerance=1e-3,
    )

    selected = {tuple(member) for member in result.truss_model.members}
    expected = {
        (0, 1), (1, 2),  # top ties AB and BC
        (3, 4),  # lower compression chord DE
        (0, 3), (1, 3), (2, 4),  # direct web struts
        (0, 5), (3, 6), (4, 7),  # frame-boundary branches
    }
    assert selected == expected
    assert result.equilibrium_residual < 1e-6


def test_frame_boundary_rejects_unbalanced_resultants():
    top, lower, boundary = _fhwa_cantilever_frame_data()
    with pytest.raises(ValueError, match="self-equilibrated"):
        optimize_frame_boundary(
            top,
            lower,
            boundary,
            top_loads=[(0.0, 0.0), (0.0, -2005.0), (0.0, -926.0)],
            boundary_forces=[(0.0, 0.0)] * 3,
        )


def test_fhwa_linear_stress_blocks_locate_compression_branches():
    layout = locate_linear_frame_boundary(
        section_width=120.0,
        thickness=96.0,
        neutral_axis_x=3.81 * 12.0,
        compression_edge_stress=1.328,
        tie_x=0.67 * 12.0,
        edge_partition_forces=[926.0],
    )

    assert layout.compression_x[0] == pytest.approx(120.0 - 0.3133 * 12.0, abs=0.1)
    assert layout.compression_x[1] == pytest.approx(7.511 * 12.0, abs=0.1)
    assert layout.compression_block_forces[0] == pytest.approx(926.0)


def test_section_actions_and_load_correspondence_recover_fhwa_topology():
    top, _, boundary = _fhwa_cantilever_frame_data()
    lower = [
        {"x": 7.52, "y": -0.198, "connect_top_indices": [0, 1]},
        {"x": 9.69, "y": -0.310, "connect_top_indices": [2]},
    ]
    result = optimize_frame_boundary_actions(
        top,
        lower,
        boundary,
        top_loads=[(0.0, 0.0), (0.0, -2005.0), (0.0, -926.0)],
        axial_compression=2931.0,
        moment_about_reference=2005.0 * 6.97 + 926.0 * 22.99,
        min_angle=25.0,
        force_tolerance=1e-3,
    )

    assert {tuple(member) for member in result.truss_model.members} == {
        (0, 1), (1, 2), (3, 4),
        (0, 3), (1, 3), (2, 4),
        (0, 5), (3, 6), (4, 7),
    }
    tie_branch = next(
        force for member, force in zip(result.truss_model.members, result.member_forces)
        if tuple(member) == (0, 5)
    )
    assert tie_branch == pytest.approx(1664.0, rel=0.02)


def test_section_actions_include_nonzero_interface_shear():
    top, _, boundary = _fhwa_cantilever_frame_data()
    lower = [
        {"x": 7.52, "y": -0.198, "connect_top_indices": [0, 1]},
        {"x": 9.69, "y": -0.310, "connect_top_indices": [2]},
    ]
    boundary = [
        *boundary,
        {"x": -4.0, "y": 8.465, "connect_group": "top", "connect_index": 0},
    ]
    top_loads = [(-100.0, 0.0), (0.0, -2005.0), (0.0, -926.0)]
    required_moment = -sum(
        x * force_y - y * force_x
        for (x, y), (force_x, force_y) in zip(top, top_loads)
    )

    result = optimize_frame_boundary_actions(
        top,
        lower,
        boundary,
        top_loads=top_loads,
        interface_shear=100.0,
        axial_compression=2931.0,
        moment_about_reference=required_moment,
        min_angle=25.0,
        force_tolerance=1e-3,
    )

    shear_branch = next(
        force for member, force in zip(result.truss_model.members, result.member_forces)
        if tuple(member) == (0, 8)
    )
    assert shear_branch == pytest.approx(-100.0)
    assert result.equilibrium_residual < 1e-6


def test_section_actions_reject_underdetermined_compression_correspondence():
    top, lower, boundary = _fhwa_cantilever_frame_data()
    with pytest.raises(ValueError, match="explicit load correspondence"):
        optimize_frame_boundary_actions(
            top,
            lower,
            boundary,
            top_loads=[(0.0, 0.0), (0.0, -2005.0), (0.0, -926.0)],
            axial_compression=2931.0,
            moment_about_reference=2005.0 * 6.97 + 926.0 * 22.99,
        )
