"""Tests for typed pier-cap models and tabular adapters."""

import numpy as np
import pytest

from stm_solver.design_checks import (
    ExternalNodalZonePlan,
    NodalFaceTributary,
    NodalZoneGeometry,
    NodalZoneGroupDefinition,
    ResolvedNodalForce,
    check_nodal_zone,
    check_strut,
    check_subdivided_nodal_zone_faces,
    check_tie,
    construct_subdivided_external_nodal_zone,
)
from stm_solver.ground_structure import ExternalFace
from stm_solver.pier_cap import (
    BearingLoad,
    FoundationSupport,
    LoadCombination,
    LoadComponent,
    LoadPointForce,
    PierCapGeometry,
    PierCapLoadSet,
    PierCapModel,
    load_pier_cap_model,
    save_pier_cap_model,
)
from stm_solver.tables import (
    design_check_records,
    export_csv_tables,
    export_excel_tables,
    ground_structure_records,
    nodal_geometry_records,
    records_to_dataframes,
)
from stm_solver.truss_extract import TrussModel


def _model():
    return PierCapModel(
        geometry=PierCapGeometry(depth=36.0, top_tie_y=33.0, bottom_tie_y=3.0),
        loads=(BearingLoad("B1", 60.0, 36.0, -200.0, 12.0),),
        supports=(
            FoundationSupport("P1", 24.0, 0.0, 18.0, restraint="pin"),
            FoundationSupport("P2", 96.0, 0.0, 18.0),
        ),
    )


def test_typed_model_runs_existing_solver_and_builds_tables():
    result = _model().solve()
    tables = ground_structure_records(result)
    assert result.equilibrium_residual < 1e-8
    assert set(tables) == {"nodes", "members", "reactions", "external_faces"}
    assert len(tables["external_faces"]) == 3
    assert tables["external_faces"][0]["inward_normal_y"] == -1.0
    assert tables["external_faces"][1]["inward_normal_y"] == 1.0
    assert {row["member_type"] for row in tables["members"]} == {"strut", "tie"}


def test_records_convert_to_dataframes():
    frames = records_to_dataframes(_model().input_records())
    assert list(frames["loads"]["id"]) == ["B1"]
    assert list(frames["supports"]["id"]) == ["P1", "P2"]


def test_typed_model_rejects_invalid_geometry_and_duplicate_ids():
    with pytest.raises(ValueError, match="bottom_tie_y"):
        PierCapGeometry(depth=36.0, top_tie_y=2.0, bottom_tie_y=3.0)
    with pytest.raises(ValueError, match="unique"):
        PierCapModel(
            geometry=PierCapGeometry(36.0, 33.0, 3.0),
            loads=(BearingLoad("X", 60.0, 36.0, -200.0, 12.0),),
            supports=(FoundationSupport("X", 24.0, 0.0, 18.0),),
        )


def test_typed_model_rejects_duplicate_locations_and_faces_outside_cap():
    geometry = PierCapGeometry(36.0, 33.0, 3.0, length=100.0)
    with pytest.raises(ValueError, match="locations must be unique"):
        PierCapModel(
            geometry,
            (
                BearingLoad("B1", 50.0, 36.0, -100.0, 10.0),
                BearingLoad("B2", 50.0, 36.0, -100.0, 10.0),
            ),
            (FoundationSupport("P1", 25.0, 0.0, 10.0),),
        )
    with pytest.raises(ValueError, match="faces extend outside"):
        PierCapModel(
            geometry,
            (BearingLoad("B1", 3.0, 36.0, -100.0, 10.0),),
            (FoundationSupport("P1", 25.0, 0.0, 10.0),),
        )


def _load_set():
    return PierCapLoadSet(
        components=(
            LoadComponent("DEAD", (
                LoadPointForce("B1", 10.0, 30.0, -10.0),
                LoadPointForce("B2", 20.0, 30.0, -20.0),
            )),
            LoadComponent("LIVE", (
                LoadPointForce("B1", 10.0, 30.0, -5.0, px=2.0),
                LoadPointForce("B2", 20.0, 30.0, -7.0),
            )),
        ),
        combinations=(
            LoadCombination("STRENGTH", {"DEAD": 1.25, "LIVE": 1.75}),
        ),
        face_widths={"B1": 12.0, "B2": 14.0},
    )


def test_load_set_assembles_named_combination_with_stable_geometry():
    loads = _load_set().assemble("STRENGTH")
    by_id = {load.id: load for load in loads}
    assert by_id["B1"].py == pytest.approx(-21.25)
    assert by_id["B1"].px == pytest.approx(3.5)
    assert by_id["B1"].face_width == pytest.approx(12.0)
    assert by_id["B2"].py == pytest.approx(-37.25)


def test_load_set_rejects_unknown_component_and_changed_location():
    with pytest.raises(ValueError, match="unknown components"):
        PierCapLoadSet(
            (LoadComponent("DEAD", (LoadPointForce("B1", 0, 0, -1),)),),
            (LoadCombination("BAD", {"LIVE": 1.0}),),
            {"B1": 1.0},
        )
    with pytest.raises(ValueError, match="changes location"):
        PierCapLoadSet(
            (
                LoadComponent("A", (LoadPointForce("B1", 0, 0, -1),)),
                LoadComponent("B", (LoadPointForce("B1", 1, 0, -1),)),
            ),
            (LoadCombination("ALL", {"A": 1.0, "B": 1.0}),),
            {"B1": 1.0},
        )


def test_load_set_validates_cap_envelope():
    with pytest.raises(ValueError, match="outside"):
        _load_set().validate_envelope(PierCapGeometry(30.0, 27.0, 3.0, length=15.0))


def test_model_json_round_trip_preserves_analysis(tmp_path):
    original = _model()
    path = tmp_path / "model.json"
    save_pier_cap_model(original, path)
    restored = load_pier_cap_model(path)

    assert restored == original
    assert restored.solve().member_forces == pytest.approx(original.solve().member_forces)


def test_result_tables_export_to_csv(tmp_path):
    tables = ground_structure_records(_model().solve())
    written = export_csv_tables(tables, tmp_path / "tables")

    assert set(written) == set(tables)
    assert written["members"].read_text(encoding="utf-8").startswith(
        "member_id,node_i,node_j,force,member_type"
    )


def test_csv_export_rejects_unsafe_table_name(tmp_path):
    with pytest.raises(ValueError, match="Unsafe"):
        export_csv_tables({"../escape": [{"value": 1}]}, tmp_path)


def test_nodal_geometry_objects_normalize_to_tables():
    geometry = NodalZoneGeometry(
        0, "CCT", ((-6.0, 0.0), (6.0, 0.0)), 10.0, 4, 30.7, 14.7,
        ((-3.0, -7.0), (3.0, 7.0)),
    )
    tributary = NodalFaceTributary(
        0, 0, "pile_head", "left", (-1.0, 0.0), (-2.0, 0.0),
        (0.0, 0.0), 2.0, 100.0,
    )
    resolved = ResolvedNodalForce(0, (1, 2), (30.0, -40.0), 50.0, 53.13)
    tables = nodal_geometry_records((geometry,), (tributary,), (resolved,))

    assert tables["nodal_zone_geometries"][0]["interface_end_y"] == 7.0
    assert tables["face_tributaries"][0]["normal_force"] == 100.0
    assert tables["resolved_nodal_forces"][0]["force_y"] == -40.0
    assert tables["nodal_zone_groups"] == []


def test_reviewed_nodal_zone_plan_normalizes_to_one_audit_table():
    model = TrussModel(
        nodes=np.array([[0, 0], [0, 10]], dtype=float),
        members=np.array([[0, 1]], dtype=int),
        member_types=['strut'], support_node_ids={}, load_node_ids={},
    )
    face = ExternalFace('pile_head', 0, 0, (0, 0), (-2, 0), (2, 0), 4)
    plan = ExternalNodalZonePlan(0, 2.0, (
        NodalZoneGroupDefinition('web', (0,), (0, 10), 'CCC'),
    ))
    groups = construct_subdivided_external_nodal_zone(
        face, model, np.array([-100.0]), plan
    )

    row = nodal_geometry_records(group_geometries=groups)["nodal_zone_groups"][0]
    assert row["label"] == "web"
    assert row["normal_force"] == pytest.approx(100.0)
    assert row["tributary_width"] == pytest.approx(4.0)
    assert row["strut_interface_width"] == pytest.approx(4.0)
    face_rows = design_check_records(
        nodal_face_checks=check_subdivided_nodal_zone_faces(
            groups[0], 8.0, 4.0
        )
    )["nodal_face_checks"]
    assert {row["face_type"] for row in face_rows} == {
        "bearing", "back", "strut_interface"
    }


def test_design_checks_normalize_to_tables():
    tables = design_check_records(
        (check_strut(0, -100.0, 10.0, 8.0, 4.0),),
        (check_tie(1, 100.0),),
        (check_nodal_zone(2, "CCT", 100.0, 12.0, 8.0, 4.0),),
    )

    assert tables["strut_checks"][0]["member_id"] == 0
    assert tables["tie_checks"][0]["As_required"] == pytest.approx(100 / 54)
    assert tables["node_checks"][0]["zone_type"] == "CCT"
    assert tables["nodal_face_checks"] == []


def test_result_tables_export_to_excel(tmp_path):
    pytest.importorskip("openpyxl")
    path = export_excel_tables(
        ground_structure_records(_model().solve()), tmp_path / "results.xlsx"
    )
    assert path.is_file()
    assert path.stat().st_size > 0
