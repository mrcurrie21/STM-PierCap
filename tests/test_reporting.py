"""Tests for concise pier-cap calculation reporting."""

from types import SimpleNamespace

import numpy as np

from stm_solver.reporting import (
    build_pier_cap_calculation_report,
    build_pier_cap_html_report,
)
from stm_solver.truss_extract import TrussModel


def test_calculation_report_exposes_defaults_results_and_scope():
    common = SimpleNamespace(
        force_reversals=(object(),), initial_candidate_count=64,
        members=tuple(range(31)), case_results={"LC1": object(), "LC2": object()},
    )
    layout = SimpleNamespace(
        bar_count=6, bar_size=5, as_provided=1.86, layers=1,
    )
    anchorage = [SimpleNamespace(
        layer="top tie", end="left", available_length=9.56,
        required_development_length=8.49,
        anchorage_type="standard 90-degree hook", status="OK",
    )]
    check = SimpleNamespace(dc_ratio=0.42)
    report = build_pier_cap_calculation_report(
        project={"name": "Test Cap"},
        cap={"length": 100.0, "depth": 30.0, "width": 40.0},
        materials={"fc_ksi": 5.0, "fy_ksi": 60.0},
        detailing={"clear_cover": 2.0, "maximum_aggregate_size": 0.75},
        code_profile={
            "name": "test profile", "resistance_factor_status": "verified",
        },
        common_analysis=common, tie_layouts={"top tie": layout},
        anchorage=anchorage, cage_reviews=[SimpleNamespace(status="OK")],
        strut_checks={"LC1": [check]},
        external_nodal_checks={"LC1": [check]},
        interior_nodal_checks={"LC1": [check]},
    )

    assert "Clear cover: 2.0 in" in report
    assert "Force reversals: 1 reversal(s), designed for both signs" in report
    assert "Maximum strut D/C: 0.420" in report
    assert "three-dimensional bar positioning" in report


def test_html_report_contains_visual_summary_and_audit_sections():
    truss = TrussModel(
        nodes=np.array([[0.0, 0.0], [50.0, 30.0], [100.0, 0.0]]),
        members=np.array([[0, 1], [1, 2], [0, 2]]),
        member_types=["strut", "strut", "tie"],
        support_node_ids={0: 0, 1: 2}, load_node_ids={0: 1},
    )
    case = SimpleNamespace(
        truss_model=truss, member_forces=np.array([-20.0, -20.0, 12.0]),
    )
    common = SimpleNamespace(
        force_reversals=(), initial_candidate_count=5,
        members=np.array([[0, 1], [1, 2], [0, 2]]),
        case_results={"Strength I": case},
    )
    layout = SimpleNamespace(
        bar_count=4, bar_size=5, as_required=1.10, as_provided=1.24,
        layers=1, status="OK",
    )
    anchor = SimpleNamespace(
        layer="bottom tie", end="left", available_length=12.0,
        required_development_length=9.0, anchorage_type="straight", status="OK",
    )
    strut_check = SimpleNamespace(
        dc_ratio=0.42, status="OK", member_id=2,
    )
    node_check = SimpleNamespace(
        dc_ratio=0.37, status="OK", node_id=1,
        group_label="load B1", face_type="bearing",
    )
    report = build_pier_cap_html_report(
        project={"name": "Test & Cap", "designer": "AB", "date": "2026-09-22"},
        cap={"length": 100.0, "depth": 30.0, "width": 40.0},
        materials={"fc_ksi": 5.0, "fy_ksi": 60.0},
        detailing={"clear_cover": 2.0, "maximum_aggregate_size": 0.75},
        code_profile={"name": "AREMA test", "resistance_factor_status": "verified"},
        common_analysis=common, tie_layouts={"bottom tie": layout},
        anchorage=[anchor], cage_reviews=[SimpleNamespace(status="OK")],
        strut_checks={"Strength I": [strut_check]},
        external_nodal_checks={"Strength I": [node_check]},
        interior_nodal_checks={"Strength I": [node_check]},
        calculation_records={"model_quality": [{
            "combination": "Strength I", "selected_member_count": 3,
            "maximum_node_degree": 2, "equilibrium_residual": 1e-9,
        }], "nodes": [
            {"node_id": 0, "x": 0.0, "y": 0.0},
            {"node_id": 1, "x": 50.0, "y": 30.0},
        ], "common_member_forces": [{
            "combination": "Strength I", "candidate_id": 2,
            "node_i": 0, "node_j": 1, "force_type": "strut", "force": -20.0,
        }]},
    )

    assert "<!doctype html>" in report
    assert "Test &amp; Cap" in report
    assert '<svg class="force-flow"' in report
    assert "Governing D/C" in report
    assert "Scope and limitations" in report
    assert "M2" in report
    assert "Node N1 - load B1 - bearing" in report
    assert "Technical calculation tables" in report
    assert "Node coordinate reference (2 nodes)" in report
    assert ">Expand all</button>" in report
    assert ">Collapse all</button>" in report
    assert "setTechnicalDetails" in report
