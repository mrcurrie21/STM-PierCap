"""Tests for AASHTO design checks module."""
from types import SimpleNamespace

import numpy as np
import pytest

from stm_solver.design_checks import (
    REBAR_TABLE,
    ExternalNodalZonePlan,
    NodalZoneGroupDefinition,
    StrutWidthProfile,
    apply_conservative_strut_policy,
    arema_2025_nodal_stress_factors,
    arema_2025_stm_resistance_factors,
    calculate_standard_hook_development,
    calculate_strut_width_profiles,
    calculate_tension_development_length,
    calculate_tension_lap_splice,
    calculate_tie_end_anchorage_geometry,
    check_interior_nodal_zone_faces,
    check_nodal_face_capacity,
    check_nodal_zone,
    check_provided_crack_control_grid,
    check_provided_tie_bar_layout,
    check_reinforcement_cage_congestion,
    check_strut,
    check_subdivided_nodal_zone_faces,
    check_tie,
    classify_nodal_zone,
    classify_strut_shape,
    classify_strut_shapes,
    construct_continuous_tie_nodal_zone,
    construct_external_nodal_zone,
    construct_single_strut_external_nodal_zone,
    construct_subdivided_external_nodal_zone,
    design_orthogonal_crack_control_grid,
    design_tie_bar_layout,
    extended_nodal_zone_anchorage_length,
    extended_strut_tie_critical_section,
    minimum_crack_control_reinforcement,
    projected_strut_interface_width,
    required_reinforced_strut_steel_area,
    resolve_member_forces_at_node,
    revise_strut_axis_through_tributary,
    select_bars,
    strut_width_at,
    subdivide_external_face,
)
from stm_solver.ground_structure import ExternalFace
from stm_solver.truss_extract import TrussModel


class TestCheckStrut:
    def test_basic_capacity(self):
        """Strut with low demand should pass."""
        sc = check_strut(0, -50, 10, 8, 4.0)
        assert sc.status == 'OK'
        assert sc.dc_ratio < 1.0

    def test_high_demand_fails(self):
        """Strut with very high demand should fail."""
        sc = check_strut(0, -10000, 2, 8, 4.0)
        assert sc.status == 'NG'
        assert sc.dc_ratio > 1.0

    def test_fcu_formula(self):
        """AASHTO fcu = f'c / (0.8 + 170*eps_1), capped at 0.85*f'c."""
        sc = check_strut(0, -100, 10, 8, 4.0, eps_1=0.002)
        expected_fcu = min(4.0 / (0.8 + 170 * 0.002), 0.85 * 4.0)
        assert abs(sc.fcu - expected_fcu) < 1e-6

    def test_phi_factor(self):
        """Resistance factor should be 0.75."""
        sc = check_strut(0, -100, 10, 8, 4.0)
        assert sc.phi == 0.75

    def test_reinforced_strut_steel_area_matches_fhwa_example(self):
        area = required_reinforced_strut_steel_area(
            1013.0, 856.0, 60.0, phi=0.70,
        )
        assert area == pytest.approx(4.67, abs=0.01)


class TestNodalFaceCapacity:
    def test_arema_2025_stm_resistance_factors(self):
        factors = arema_2025_stm_resistance_factors()
        assert factors["compression"] == pytest.approx(0.70)
        assert factors["reinforced_concrete_tension"] == pytest.approx(0.90)
        assert factors["anchorage_zone_compression"] == pytest.approx(0.80)
        assert factors["anchorage_zone_tension_steel"] == pytest.approx(1.00)

    def test_arema_2025_face_specific_efficiency_factors(self):
        factors = arema_2025_nodal_stress_factors(5.0)
        assert factors["CCC"]["bearing"] == pytest.approx(0.85)
        assert factors["CCT"]["bearing"] == pytest.approx(0.70)
        assert factors["CTT"]["bearing"] == pytest.approx(0.60)
        assert factors["CCC"]["strut_interface"] == pytest.approx(0.60)

    def test_arema_without_crack_grid_uses_point_four_five(self):
        factors = arema_2025_nodal_stress_factors(5.0, crack_control=False)
        assert all(
            value == pytest.approx(0.45)
            for faces in factors.values() for value in faces.values()
        )

    def test_matches_fhwa_cct_strut_interface(self):
        check = check_nodal_face_capacity(
            1177.0, 706.0 / 48.0, 48.0, 5.0, 0.60, phi=0.70,
            zone_type="CCT", face_type="strut_interface",
        )
        assert check.area == pytest.approx(706.0)
        assert check.capacity == pytest.approx(1482.0, abs=1.0)
        assert check.dc_ratio == pytest.approx(0.7942, abs=0.001)
        assert check.status == "OK"

    def test_preserves_failing_intermediate_state(self):
        check = check_nodal_face_capacity(
            1177.0, 542.0 / 48.0, 48.0, 5.0, 0.60, phi=0.70,
        )
        assert check.capacity == pytest.approx(1138.0, abs=1.0)
        assert check.status == "NG"

    def test_allows_zero_demand_face(self):
        check = check_nodal_face_capacity(0.0, 2.0, 8.0, 4.0, 0.85)
        assert check.dc_ratio == 0.0
        assert check.status == "OK"


class TestStrutShapeClassification:
    @staticmethod
    def _profile(width_i, width_j):
        return StrutWidthProfile(
            member_id=4, node_i=1, node_j=2,
            width_i=width_i, width_j=width_j,
            controlling_width=min(width_i, width_j),
            maximum_width=max(width_i, width_j),
            profile_type="prismatic" if width_i == width_j else "tapered",
            status="complete",
        )

    def test_equal_profile_is_prismatic(self):
        result = classify_strut_shape(self._profile(8.0, 8.0))
        assert result.shape == "prismatic"
        assert result.expansion_ratio == pytest.approx(1.0)
        assert not result.field_evidence_required

    def test_midspan_expansion_is_bottle_shaped(self):
        result = classify_strut_shape(
            self._profile(8.0, 10.0), midspan_width=16.0
        )
        assert result.shape == "bottle-shaped"
        assert result.expansion_ratio == pytest.approx(2.0)

    def test_fan_shape_requires_explicit_designation(self):
        profile = self._profile(8.0, 12.0)
        assert classify_strut_shape(profile).shape == "tapered"
        result = classify_strut_shape(profile, represents_fan_field=True)
        assert result.shape == "fan-shaped"
        assert "explicit" in result.basis

    def test_batch_rejects_unknown_evidence_member(self):
        with pytest.raises(ValueError, match="unknown members"):
            classify_strut_shapes(
                [self._profile(8.0, 8.0)], midspan_widths={99: 12.0}
            )

    def test_simplified_policy_uses_minimum_width_and_bottle_detailing(self):
        profile = self._profile(8.0, 12.0)
        classification = classify_strut_shape(profile)
        design = apply_conservative_strut_policy(
            [profile], [classification]
        )[0]
        assert design.capacity_width == pytest.approx(8.0)
        assert design.design_shape == "bottle-shaped-conservative"
        assert not design.fan_spreading_credit
        assert design.orthogonal_crack_control_required


class TestCrackControlGrid:
    def test_checks_user_provided_area_and_spacing(self):
        grid = check_provided_crack_control_grid(
            42.0, 27.0,
            {
                "vertical": {"steel_area_per_spacing": 0.62, "spacing": 4.5},
                "horizontal": {"steel_area_per_spacing": 0.62, "spacing": 4.5},
            },
        )
        assert {item.direction for item in grid} == {"vertical", "horizontal"}
        assert all(item.provided_ratio == pytest.approx(0.62 / (42.0 * 4.5)) for item in grid)
        assert all(item.status == "OK" for item in grid)

    def test_arema_ratio_and_spacing_limits(self):
        vertical, horizontal = design_orthogonal_crack_control_grid(
            42.0, 27.0, bar_size=5, legs=2
        )
        assert vertical.selected_spacing == pytest.approx(4.5)
        assert vertical.spacing_limit == pytest.approx(6.75)
        assert vertical.provided_ratio >= 0.003
        assert vertical.status == "OK"
        assert horizontal.selected_spacing == pytest.approx(vertical.selected_spacing)
        assert horizontal.provided_ratio == pytest.approx(vertical.provided_ratio)

    @pytest.mark.parametrize("bar_size, legs", [(99, 2), (5, 0)])
    def test_rejects_invalid_bar_configuration(self, bar_size, legs):
        with pytest.raises(ValueError):
            design_orthogonal_crack_control_grid(
                42.0, 27.0, bar_size=bar_size, legs=legs
            )


class TestTieBarLayout:
    def test_checks_compact_user_provided_layout(self):
        layout = check_provided_tie_bar_layout(
            1.50, 42.0, bar_count=5, bar_size=5,
            maximum_aggregate_size=0.75,
        )
        assert layout.as_provided == pytest.approx(1.55)
        assert layout.status == "OK"

    def test_selects_minimum_area_layout_that_fits(self):
        layout = design_tie_bar_layout(4.2, 42.0)
        assert layout.as_provided >= 4.2
        assert layout.status == "OK"
        assert layout.transverse_clear_spacing >= 1.5
        assert layout.transverse_center_spacing <= 12.0
        assert layout.layers <= 2
        assert sum(layout.bars_per_layer) == layout.bar_count

    def test_accounts_for_cover_and_enclosure(self):
        layout = design_tie_bar_layout(
            3.0, 18.0, clear_cover=2.0, enclosure_bar_size=5,
        )
        assert layout.clear_cover == pytest.approx(2.0)
        assert layout.enclosure_bar_size == 5
        assert layout.transverse_clear_spacing >= 1.5
        assert layout.transverse_center_spacing <= 12.0

    def test_rejects_layout_that_cannot_fit(self):
        with pytest.raises(ValueError, match="No permitted tie-bar arrangement"):
            design_tie_bar_layout(
                20.0, 10.0, tie_zone_depth=3.0, maximum_layers=1,
            )

    def test_enforces_aggregate_dependent_clear_spacing(self):
        layout = design_tie_bar_layout(
            2.0, 42.0, maximum_aggregate_size=1.0,
        )
        assert layout.required_transverse_clear_spacing >= 2.0
        assert layout.transverse_clear_spacing >= 2.0
        assert layout.maximum_aggregate_size == pytest.approx(1.0)

    def test_rejects_invalid_aggregate_size(self):
        with pytest.raises(ValueError, match="maximum_aggregate_size"):
            design_tie_bar_layout(2.0, 42.0, maximum_aggregate_size=0.0)


class TestTieAnchorageGeometry:
    def test_calculates_available_lengths_without_inventing_requirement(self):
        left, right = calculate_tie_end_anchorage_geometry(
            "top", [6.5, 36.0, 57.5, 185.5], 0.0, 201.0, 6,
        )
        end_offset = 2.0 + 0.625 + 0.5 * 0.75
        assert left.available_length == pytest.approx(21.25 - end_offset)
        assert right.available_length == pytest.approx(
            201.0 - end_offset - 0.5 * (185.5 + 57.5)
        )
        assert left.required_development_length is None
        assert left.status == "REVIEW"

    def test_compares_supplied_governing_development_lengths(self):
        geometries = calculate_tie_end_anchorage_geometry(
            "bottom", [36.0, 57.5, 156.0], 0.0, 201.0, 5,
            required_development_lengths={"left": 40.0, "right": 100.0},
            anchorage_type="hooked",
        )
        assert geometries[0].status == "OK"
        assert geometries[1].status == "NG"
        assert all(item.anchorage_type == "hooked" for item in geometries)

    def test_accepts_end_specific_anchorage_types(self):
        geometries = calculate_tie_end_anchorage_geometry(
            "top", [20.0, 60.0, 100.0], 0.0, 120.0, 6,
            required_development_lengths={"left": 10.0, "right": 20.0},
            anchorage_type={"left": "standard 90-degree hook", "right": "straight"},
        )
        assert geometries[0].anchorage_type == "standard 90-degree hook"
        assert geometries[1].anchorage_type == "straight"

    def test_fhwa_extended_nodal_zone_geometry(self):
        available = extended_nodal_zone_anchorage_length(
            14.0, 10.0, 30.7, 5.0, 2.0,
        )
        assert available == pytest.approx(25.4, abs=0.1)

    def test_accepts_extended_strut_critical_section_override(self):
        left, right = calculate_tie_end_anchorage_geometry(
            "top", [20.0, 60.0, 100.0], 0.0, 120.0, 6,
            required_development_lengths={"left": 10.0, "right": 10.0},
            critical_section_coordinates={"left": 25.0, "right": 95.0},
            critical_section_basis={
                "left": "extended strut left", "right": "extended strut right",
            },
        )
        assert left.critical_section_coordinate == pytest.approx(25.0)
        assert right.critical_section_coordinate == pytest.approx(95.0)
        assert left.basis.startswith("extended strut left")

    def test_intersects_extended_strut_edges_with_tie(self):
        geometry = SimpleNamespace(
            revised_axis=SimpleNamespace(start=(0.0, 0.0), end=(10.0, 10.0)),
            strut_interface=((0.0, 0.0), (2.0, -2.0)),
        )
        assert extended_strut_tie_critical_section(
            geometry, 10.0, "left"
        ) == pytest.approx(14.0)
        assert extended_strut_tie_critical_section(
            geometry, 10.0, "right"
        ) == pytest.approx(10.0)


class TestReinforcementCageReview:
    def test_passes_aggregate_spacing_hook_fit_and_anchorage(self):
        layout = design_tie_bar_layout(
            1.7, 42.0, maximum_aggregate_size=0.75,
        )
        review = check_reinforcement_cage_congestion(
            "top", layout, member_depth=30.0,
            crack_control_bar_size=5, crack_control_spacing=4.5,
            maximum_aggregate_size=0.75, hook_projections=(8.0,),
            anchorage_statuses=("OK", "OK"),
        )
        assert review.status == "OK"
        assert review.required_crack_control_clear_spacing == pytest.approx(1.5)

    def test_fails_unresolved_anchorage(self):
        layout = design_tie_bar_layout(
            1.7, 42.0, maximum_aggregate_size=0.75,
        )
        review = check_reinforcement_cage_congestion(
            "top", layout, member_depth=30.0,
            crack_control_bar_size=5, crack_control_spacing=4.5,
            maximum_aggregate_size=0.75,
        )
        assert review.anchorage_status == "REVIEW"
        assert review.status == "NG"


class TestTensionDevelopmentLength:
    def test_arema_basic_equation_and_minimum(self):
        result = calculate_tension_development_length(6, 60.0, 4.0)
        expected = 0.0759 * 0.75 * 60000.0 / np.sqrt(4000.0)
        assert result.basic_length == pytest.approx(expected)
        assert result.required_length == pytest.approx(expected)
        assert result.basis.startswith("AREMA 2025 Section 2.14")

    def test_applies_bounded_confinement_and_top_factor(self):
        result = calculate_tension_development_length(
            6, 60.0, 4.0, top_bar=True, cover=3.0,
            clear_spacing=11.25, transverse_reinforcement_area=0.62,
            transverse_spacing=4.5, bars_in_splitting_plane=4,
        )
        assert result.confinement_factor == pytest.approx(0.4)
        assert result.top_bar_factor == pytest.approx(1.4)
        assert result.required_length == pytest.approx(
            result.basic_length * 1.4 * 0.4
        )

    def test_enforces_twelve_inch_minimum(self):
        result = calculate_tension_development_length(
            3, 40.0, 10.0, cover=6.0, clear_spacing=12.0,
        )
        assert result.calculated_length < 12.0
        assert result.required_length == 12.0

    def test_caps_combined_top_and_epoxy_factor(self):
        result = calculate_tension_development_length(
            8, 60.0, 4.0, top_bar=True, epoxy_coated=True,
            cover=2.0, clear_spacing=2.0,
        )
        assert result.epoxy_factor == 1.5
        assert result.combined_top_epoxy_factor == 1.7

    def test_excess_reinforcement_reduction_is_explicit(self):
        conservative = calculate_tension_development_length(5, 60.0, 4.0)
        reduced = calculate_tension_development_length(
            5, 60.0, 4.0, apply_excess_reinforcement_factor=True,
            as_required=1.0, as_provided=2.0,
        )
        assert conservative.excess_reinforcement_factor == 1.0
        assert reduced.excess_reinforcement_factor == 0.5
        assert reduced.required_length >= 12.0


class TestStandardHookDevelopment:
    def test_arema_hook_equation_and_geometry(self):
        result = calculate_standard_hook_development(6, 60.0, 5.0)
        expected = 0.02 * 0.75 * 60000.0 / np.sqrt(5000.0)
        assert result.basic_length == pytest.approx(expected)
        assert result.inside_bend_diameter == pytest.approx(6.0 * 0.75)
        assert result.tail_extension == pytest.approx(12.0 * 0.75)
        assert result.transverse_projection == pytest.approx(16.0 * 0.75)

    def test_cover_factor_and_minimum(self):
        result = calculate_standard_hook_development(
            3, 40.0, 10.0, adequate_cover=True,
        )
        assert result.cover_factor == 0.8
        assert result.required_length == 6.0

    def test_rejects_nonstandard_angle(self):
        with pytest.raises(ValueError, match="90 or 180"):
            calculate_standard_hook_development(6, 60.0, 5.0, hook_angle=135)


class TestTensionLapSplice:
    def test_defaults_to_class_b(self):
        result = calculate_tension_lap_splice(6, 20.0)
        assert result.splice_class == "B"
        assert result.required_length == pytest.approx(26.0)

    def test_class_a_requires_both_conditions(self):
        result = calculate_tension_lap_splice(
            6, 20.0, provided_area_ratio=2.0, fraction_spliced=0.5,
        )
        assert result.splice_class == "A"
        assert result.required_length == pytest.approx(20.0)

    def test_flags_lap_as_prohibited_for_tension_tie(self):
        result = calculate_tension_lap_splice(
            6, 20.0, tension_tie_member=True,
        )
        assert not result.permitted_for_tension_tie_member


class TestCheckTie:
    def test_basic(self):
        tc = check_tie(0, 50, 60.0)
        assert tc.As_required > 0
        assert tc.As_provided >= tc.As_required
        assert tc.status == 'OK'

    def test_as_formula(self):
        """As = Tu / (phi * fy)."""
        tc = check_tie(0, 100, 60.0)
        expected_As = 100 / (0.90 * 60.0)
        assert abs(tc.As_required - expected_As) < 1e-6

    def test_phi_factor(self):
        tc = check_tie(0, 50, 60.0)
        assert tc.phi == 0.90

    def test_configurable_factor_and_bar_size(self):
        tc = check_tie(0, 100, 60.0, phi=0.85, preferred_bar_size=8)
        assert tc.As_required == pytest.approx(100 / (0.85 * 60.0))
        assert tc.bar_size == 8
        assert tc.As_provided >= tc.As_required


class TestSelectBars:
    def test_minimum_two_bars(self):
        """Should always provide at least 2 bars."""
        sz, n, As = select_bars(0.1)
        assert n >= 2

    def test_sufficient_area(self):
        """Provided area should be >= required."""
        for As_req in [0.5, 1.0, 3.0, 5.0, 10.0]:
            sz, n, As = select_bars(As_req)
            assert As >= As_req


class TestCheckNodalZone:
    def test_ccc_node(self):
        nc = check_nodal_zone(0, 'CCC', 100, 8, 8, 4.0)
        assert nc.fcu_node == pytest.approx(0.85 * 4.0)

    def test_cct_node(self):
        nc = check_nodal_zone(0, 'CCT', 100, 8, 8, 4.0)
        assert nc.fcu_node == pytest.approx(0.75 * 4.0)

    def test_ctt_node(self):
        nc = check_nodal_zone(0, 'CTT', 100, 8, 8, 4.0)
        assert nc.fcu_node == pytest.approx(0.65 * 4.0)


def test_run_all_checks_uses_external_face_width():
    from stm_solver.design_checks import run_all_checks

    tm = TrussModel(
        nodes=np.array([[0, 0], [0, 10]], dtype=float),
        members=np.array([[0, 1]], dtype=int),
        member_types=['strut'],
        support_node_ids={0: 0},
        load_node_ids={0: 1},
        external_faces=[
            ExternalFace('pile_head', 0, 0, (0, 0), (-6, 0), (6, 0), 12),
            ExternalFace('bearing_plate', 0, 1, (0, 10), (-3, 10), (3, 10), 6),
        ],
    )
    _, _, node_checks = run_all_checks(
        tm, np.array([-100.0]), [], [], 4.0, 60.0, 8.0,
        bearing_width=99.0,
    )

    checks = {check.node_id: check for check in node_checks}
    assert checks[0].bearing_area == pytest.approx(12.0 * 8.0)
    assert checks[1].bearing_area == pytest.approx(6.0 * 8.0)


class TestExternalNodalZoneGeometry:
    @staticmethod
    def _single_strut_model(angle_degrees, *, tension_tie=False):
        theta = np.radians(angle_degrees)
        nodes = [[0.0, 0.0], [-10.0 * np.cos(theta), 10.0 * np.sin(theta)]]
        members = [[0, 1]]
        member_types = ['strut']
        forces = [-1177.0]
        if tension_tie:
            nodes.append([-10.0, 0.0])
            members.append([0, 2])
            member_types.append('tie')
            forces.append(1013.0)
        return TrussModel(
            nodes=np.asarray(nodes),
            members=np.asarray(members),
            member_types=member_types,
            support_node_ids={0: 0},
            load_node_ids={},
        ), np.asarray(forces)

    def test_fhwa_example_1_node_c_projected_interface_width(self):
        """FHWA-NHI-130126, Design Example 1, pp. 1-18 to 1-19."""
        model, forces = self._single_strut_model(30.7, tension_tie=True)
        face = ExternalFace(
            'pile_head', 0, 0, (0.0, 0.0), (-6.0, 0.0), (6.0, 0.0), 12.0
        )

        geometry = construct_external_nodal_zone(face, model, forces, 10.0)

        assert geometry.zone_type == 'CCT'
        assert geometry.strut_angle_degrees == pytest.approx(30.7)
        assert geometry.strut_interface_width == pytest.approx(14.7, abs=0.05)
        p1, p2 = map(np.asarray, geometry.strut_interface)
        assert np.linalg.norm(p2 - p1) == pytest.approx(
            geometry.strut_interface_width
        )

    def test_fhwa_example_1_node_f_projected_interface_width(self):
        """FHWA-NHI-130126, Design Example 1, pp. 1-23 to 1-24."""
        model, forces = self._single_strut_model(30.7)
        face = ExternalFace(
            'bearing_plate', 0, 0, (0.0, 0.0), (-6.0, 0.0), (6.0, 0.0), 12.0
        )

        geometry = construct_external_nodal_zone(face, model, forces, 6.0)

        assert geometry.zone_type == 'CCC'
        assert geometry.strut_interface_width == pytest.approx(11.3, abs=0.05)

    def test_multiple_struts_require_explicit_node_subdivision(self):
        model = TrussModel(
            nodes=np.array([[0, 0], [-10, 10], [10, 10]], dtype=float),
            members=np.array([[0, 1], [0, 2]], dtype=int),
            member_types=['strut', 'strut'],
            support_node_ids={0: 0},
            load_node_ids={},
        )
        face = ExternalFace(
            'pile_head', 0, 0, (0.0, 0.0), (-6.0, 0.0), (6.0, 0.0), 12.0
        )

        with pytest.raises(ValueError, match="subdivide"):
            construct_external_nodal_zone(
                face, model, np.array([-100.0, -100.0]), 10.0
            )

    def test_fhwa_example_3_node_g_face_subdivision(self):
        """FHWA-NHI-130126, Design Example 3, pp. 3-31 to 3-32."""
        face = ExternalFace(
            'column_face', 0, 0, (12.6, 0.0), (0.0, 0.0), (25.2, 0.0), 25.2
        )
        resolved_left_vertical = 787.2 * np.sin(np.radians(21.14))
        net_bearing_force = 864.7 - 32.2
        tributaries = subdivide_external_face(
            face,
            [resolved_left_vertical, net_bearing_force - resolved_left_vertical],
            labels=['left', 'right'],
        )

        assert tributaries[0].width == pytest.approx(8.59, abs=0.01)
        assert tributaries[1].width == pytest.approx(16.61, abs=0.01)
        assert sum(item.width for item in tributaries) == pytest.approx(25.2)
        assert sum(item.normal_force for item in tributaries) == pytest.approx(
            net_bearing_force
        )
        assert tributaries[0].end == pytest.approx(tributaries[1].start)

        revised_right = revise_strut_axis_through_tributary(
            tributaries[1], (12.6 + 103.44, 61.44)
        )
        assert revised_right.angle_degrees == pytest.approx(31.79, abs=0.01)
        assert projected_strut_interface_width(
            tributaries[0].width, 12.0, 21.14
        ) == pytest.approx(14.29, abs=0.01)
        assert projected_strut_interface_width(
            tributaries[1].width, 12.0, revised_right.angle_degrees
        ) == pytest.approx(18.95, abs=0.01)

    def test_fhwa_example_3_resolves_struts_at_node_g(self):
        """FHWA-NHI-130126, Design Example 3, p. 3-32."""
        model = TrussModel(
            nodes=np.array([
                [0.0, 0.0],
                [-3.64, 5.12],
                [-3.64, -5.00],
            ]),
            members=np.array([[0, 1], [0, 2]]),
            member_types=['strut', 'strut'],
            support_node_ids={},
            load_node_ids={},
        )
        resolved = resolve_member_forces_at_node(
            model, np.array([-802.0, -457.3]), 0, [0, 1]
        )

        # FHWA displays coordinates and member lengths at different rounded
        # precisions, producing a small reconstruction drift in components.
        assert resolved.vector[0] == pytest.approx(734.2, abs=0.5)
        assert resolved.vector[1] == pytest.approx(-283.9, abs=0.5)
        assert resolved.magnitude == pytest.approx(787.2, abs=0.5)
        assert resolved.angle_degrees == pytest.approx(21.14, abs=0.05)

    def test_member_force_resolution_requires_connected_members(self):
        model = TrussModel(
            nodes=np.array([[0, 0], [1, 0], [2, 0]], dtype=float),
            members=np.array([[0, 1], [1, 2]], dtype=int),
            member_types=['tie', 'tie'],
            support_node_ids={},
            load_node_ids={},
        )
        with pytest.raises(ValueError, match="not connected"):
            resolve_member_forces_at_node(
                model, np.array([10.0, 10.0]), 0, [0, 1]
            )

    def test_reviewed_plan_constructs_complete_subdivided_node(self):
        model = TrussModel(
            nodes=np.array([[0, 0], [-10, 10], [10, 10]], dtype=float),
            members=np.array([[0, 1], [0, 2]], dtype=int),
            member_types=['strut', 'strut'],
            support_node_ids={0: 0},
            load_node_ids={},
        )
        face = ExternalFace(
            'pile_head', 0, 0, (0.0, 0.0), (-6.0, 0.0), (6.0, 0.0), 12.0
        )
        plan = ExternalNodalZonePlan(
            node_id=0,
            back_face_depth=6.0,
            groups=(
                NodalZoneGroupDefinition('left', (0,), (-10.0, 10.0), 'CCC'),
                NodalZoneGroupDefinition('right', (1,), (10.0, 10.0), 'CCT'),
            ),
        )

        geometries = construct_subdivided_external_nodal_zone(
            face, model, np.array([-100.0, -100.0]), plan
        )

        assert [item.tributary.width for item in geometries] == pytest.approx([6, 6])
        assert [item.zone_type for item in geometries] == ['CCC', 'CCT']
        assert geometries[0].revised_axis.start == pytest.approx((-3.0, 0.0))
        assert geometries[1].revised_axis.start == pytest.approx((3.0, 0.0))
        assert all(item.strut_interface_width > 0.0 for item in geometries)

        checks = check_subdivided_nodal_zone_faces(
            geometries[0], 8.0, 4.0, phi=0.75,
            stress_factors={"CCC": {
                "bearing": 0.85, "back": 0.80, "strut_interface": 0.70,
            }},
        )
        by_face = {check.face_type: check for check in checks}
        assert set(by_face) == {"bearing", "back", "strut_interface"}
        assert by_face["bearing"].demand == pytest.approx(100 / np.sqrt(2))
        assert by_face["back"].demand == pytest.approx(100 / np.sqrt(2))
        assert by_face["strut_interface"].demand == pytest.approx(100.0)
        assert by_face["bearing"].area == pytest.approx(6.0 * 8.0)
        assert by_face["back"].area == pytest.approx(6.0 * 8.0)
        assert by_face["strut_interface"].stress_factor == pytest.approx(0.70)

    def test_nodal_face_checks_reject_invalid_confinement(self):
        model = TrussModel(
            nodes=np.array([[0, 0], [0, 10]], dtype=float),
            members=np.array([[0, 1]], dtype=int),
            member_types=['strut'], support_node_ids={}, load_node_ids={},
        )
        face = ExternalFace('pile_head', 0, 0, (0, 0), (-2, 0), (2, 0), 4)
        plan = ExternalNodalZonePlan(0, 2.0, (
            NodalZoneGroupDefinition('web', (0,), (0, 10), 'CCC'),
        ))
        geometry = construct_subdivided_external_nodal_zone(
            face, model, np.array([-100.0]), plan
        )[0]
        with pytest.raises(ValueError, match="confinement_factor"):
            check_subdivided_nodal_zone_faces(
                geometry, 8.0, 4.0, confinement_factor=2.1
            )

    def test_single_strut_constructor_builds_guarded_complete_geometry(self):
        model = TrussModel(
            nodes=np.array([[0, 0], [0, 10]], dtype=float),
            members=np.array([[0, 1]], dtype=int),
            member_types=['strut'], support_node_ids={0: 0}, load_node_ids={},
        )
        face = ExternalFace('pile_head', 0, 0, (0, 0), (-3, 0), (3, 0), 6)
        geometry = construct_single_strut_external_nodal_zone(
            face, model, np.array([-100.0]), 4.0, label="P1"
        )
        assert geometry.label == "P1"
        assert geometry.tributary.width == pytest.approx(6.0)
        assert geometry.strut_interface_width == pytest.approx(6.0)

        multi_model = TrussModel(
            nodes=np.array([[0, 0], [-1, 10], [1, 10]], dtype=float),
            members=np.array([[0, 1], [0, 2]], dtype=int),
            member_types=['strut', 'strut'], support_node_ids={}, load_node_ids={},
        )
        with pytest.raises(ValueError, match="explicit reviewed plan"):
            construct_single_strut_external_nodal_zone(
                face, multi_model, np.array([-50.0, -50.0]), 4.0
            )

    def test_reviewed_plan_rejects_overlapping_member_groups(self):
        model = TrussModel(
            nodes=np.array([[0, 0], [0, 10]], dtype=float),
            members=np.array([[0, 1]], dtype=int),
            member_types=['strut'], support_node_ids={}, load_node_ids={},
        )
        face = ExternalFace(
            'pile_head', 0, 0, (0.0, 0.0), (-1.0, 0.0), (1.0, 0.0), 2.0
        )
        plan = ExternalNodalZonePlan(0, 2.0, (
            NodalZoneGroupDefinition('a', (0,), (0, 10), 'CCC'),
            NodalZoneGroupDefinition('b', (0,), (0, 10), 'CCC'),
        ))
        with pytest.raises(ValueError, match="more than one"):
            construct_subdivided_external_nodal_zone(
                face, model, np.array([-100.0]), plan
            )

    def test_face_subdivision_rejects_nonpositive_force_tributaries(self):
        face = ExternalFace(
            'bearing_plate', 0, 0, (5.0, 0.0), (0.0, 0.0), (10.0, 0.0), 10.0
        )
        with pytest.raises(ValueError, match="positive and finite"):
            subdivide_external_face(face, [100.0, 0.0])

    def test_strut_width_profile_uses_both_nodal_interfaces(self):
        model = TrussModel(
            nodes=np.array([[0, 0], [10, 10]], dtype=float),
            members=np.array([[0, 1]], dtype=int),
            member_types=['strut'], support_node_ids={}, load_node_ids={},
        )
        forces = np.array([-100.0])
        lower = ExternalFace(
            'pile_head', 0, 0, (0, 0), (-3, 3), (3, -3), 6 * np.sqrt(2),
            inward_normal=(1 / np.sqrt(2), 1 / np.sqrt(2)),
        )
        upper = ExternalFace(
            'bearing_plate', 0, 1, (10, 10), (8, 12), (12, 8), 4 * np.sqrt(2),
            inward_normal=(-1 / np.sqrt(2), -1 / np.sqrt(2)),
        )
        geometries = (
            construct_single_strut_external_nodal_zone(
                lower, model, forces, 2.0, label='lower'
            ),
            construct_single_strut_external_nodal_zone(
                upper, model, forces, 2.0, label='upper'
            ),
        )

        profile = calculate_strut_width_profiles(model, forces, geometries)[0]

        assert profile.status == 'complete'
        assert profile.profile_type == 'tapered'
        assert profile.width_i == pytest.approx(6 * np.sqrt(2))
        assert profile.width_j == pytest.approx(4 * np.sqrt(2))
        assert profile.controlling_width == pytest.approx(4 * np.sqrt(2))
        assert strut_width_at(profile, 0.5) == pytest.approx(5 * np.sqrt(2))

    def test_strut_width_profile_preserves_unresolved_end(self):
        model = TrussModel(
            nodes=np.array([[0, 0], [0, 10]], dtype=float),
            members=np.array([[0, 1]], dtype=int),
            member_types=['strut'], support_node_ids={}, load_node_ids={},
        )
        forces = np.array([-100.0])
        face = ExternalFace('pile_head', 0, 0, (0, 0), (-3, 0), (3, 0), 6)
        geometry = construct_single_strut_external_nodal_zone(
            face, model, forces, 4.0
        )

        profile = calculate_strut_width_profiles(model, forces, [geometry])[0]

        assert profile.status == 'partial'
        assert profile.width_i == pytest.approx(6.0)
        assert profile.width_j is None
        assert profile.controlling_width is None
        with pytest.raises(ValueError, match="Both nodal end widths"):
            strut_width_at(profile, 0.5)

    def test_continuous_tie_node_completes_strut_end_width(self):
        model = TrussModel(
            nodes=np.array([[-10, 0], [0, 0], [10, 0], [0, 10]], dtype=float),
            members=np.array([[0, 1], [1, 2], [1, 3]], dtype=int),
            member_types=['tie', 'tie', 'strut'],
            support_node_ids={}, load_node_ids={},
        )
        forces = np.array([50.0, 50.0, -100.0])

        geometry = construct_continuous_tie_nodal_zone(
            model, forces, 1, back_face_depth=4.0
        )[0]

        assert geometry.member_ids == (2,)
        assert geometry.zone_type == 'CCT'
        assert geometry.tributary.width == pytest.approx(10.0)
        assert geometry.strut_interface_width == pytest.approx(10.0)
        polygon = np.asarray(geometry.nodal_polygon)
        assert polygon[:, 1].min() == pytest.approx(-2.0)
        assert polygon[:, 1].max() == pytest.approx(2.0)
        checks = check_interior_nodal_zone_faces(
            geometry, b=12.0, fc_prime=5.0,
        )
        assert {item.face_type for item in checks} == {
            "tie_boundary", "opposite_boundary", "strut_interface",
        }
        assert all(item.status == "OK" for item in checks)

    def test_interior_capacity_rejects_external_geometry(self):
        model = TrussModel(
            nodes=np.array([[0, 0], [0, 10]], dtype=float),
            members=np.array([[0, 1]], dtype=int),
            member_types=["strut"], support_node_ids={}, load_node_ids={},
        )
        face = ExternalFace("pile_head", 0, 0, (0, 0), (-3, 0), (3, 0), 6)
        geometry = construct_single_strut_external_nodal_zone(
            face, model, np.array([-50.0]), 4.0,
        )
        with pytest.raises(ValueError, match="interior-tie"):
            check_interior_nodal_zone_faces(geometry, 12.0, 5.0)

    def test_continuous_tie_node_rejects_struts_on_both_sides(self):
        model = TrussModel(
            nodes=np.array([
                [-10, 0], [0, 0], [10, 0], [0, 10], [0, -10],
            ], dtype=float),
            members=np.array([[0, 1], [1, 2], [1, 3], [1, 4]], dtype=int),
            member_types=['tie', 'tie', 'strut', 'strut'],
            support_node_ids={}, load_node_ids={},
        )
        with pytest.raises(ValueError, match="both sides"):
            construct_continuous_tie_nodal_zone(
                model, np.array([50.0, 50.0, -100.0, -100.0]), 1, 4.0
            )

    def test_declared_continuous_reinforcement_splits_opposite_strut_sides(self):
        model = TrussModel(
            nodes=np.array([
                [-10, 0], [0, 0], [10, 0], [0, 10], [0, -10],
            ], dtype=float),
            members=np.array([[0, 1], [1, 3], [1, 4]], dtype=int),
            member_types=['tie', 'strut', 'strut'],
            support_node_ids={}, load_node_ids={},
        )
        geometries = construct_continuous_tie_nodal_zone(
            model, np.array([50.0, -100.0, -100.0]), 1, 4.0,
            assume_continuous_reinforcement=True,
            split_opposite_sides=True,
        )

        assert {geometry.member_ids for geometry in geometries} == {(1,), (2,)}
        assert all(geometry.tributary.width == pytest.approx(10.0)
                   for geometry in geometries)

    def test_parallel_compression_uses_rectangular_node_side_face(self):
        model = TrussModel(
            nodes=np.array([[-10, 0], [0, 0], [10, 0]], dtype=float),
            members=np.array([[0, 1], [1, 2]], dtype=int),
            member_types=['tie', 'strut'],
            support_node_ids={}, load_node_ids={},
        )
        geometry = construct_continuous_tie_nodal_zone(
            model, np.array([50.0, -75.0]), 1, 4.0,
            assume_continuous_reinforcement=True,
            tie_axis=(1.0, 0.0),
            tie_boundary_points=((-12.0, 0.0), (12.0, 0.0)),
        )[0]

        assert geometry.member_ids == (1,)
        assert geometry.tributary.parent_kind == 'interior_tie_side_face'
        assert geometry.strut_interface_width == pytest.approx(4.0)


class TestClassifyNodalZone:
    def test_all_compression(self):
        tm = TrussModel(
            nodes=np.array([[0, 0], [10, 0], [5, 5]], dtype=float),
            members=np.array([[0, 2], [1, 2]], dtype=int),
            member_types=['strut', 'strut'],
            support_node_ids={}, load_node_ids={},
        )
        forces = np.array([-50, -50])  # both compression
        assert classify_nodal_zone(2, tm, forces) == 'CCC'

    def test_one_tension(self):
        tm = TrussModel(
            nodes=np.array([[0, 0], [10, 0], [5, 5]], dtype=float),
            members=np.array([[0, 2], [1, 2], [0, 1]], dtype=int),
            member_types=['strut', 'strut', 'tie'],
            support_node_ids={}, load_node_ids={},
        )
        forces = np.array([-50, -50, 30])
        # Node 0 connects to member 0 (-50) and member 2 (+30)
        assert classify_nodal_zone(0, tm, forces) == 'CCT'

    def test_collinear_chord_segments_are_one_tie_axis(self):
        tm = TrussModel(
            nodes=np.array([[-10, 0], [0, 0], [10, 0], [0, 10]], dtype=float),
            members=np.array([[0, 1], [1, 2], [1, 3]], dtype=int),
            member_types=['tie', 'tie', 'strut'],
            support_node_ids={}, load_node_ids={},
        )
        assert classify_nodal_zone(1, tm, np.array([50, 50, -100])) == 'CCT'


class TestMinCrackControl:
    def test_formula(self):
        Av, _, _ = minimum_crack_control_reinforcement(8, 12, 60.0)
        assert abs(Av - 0.003 * 8 * 12) < 1e-10


class TestRebarTable:
    def test_known_sizes(self):
        assert REBAR_TABLE[8]['db'] == pytest.approx(1.000)
        assert REBAR_TABLE[8]['Ab'] == pytest.approx(0.79)
        assert REBAR_TABLE[11]['Ab'] == pytest.approx(1.56)
