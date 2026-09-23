"""Regression tests against source-traceable STM design examples."""

from pathlib import Path

import pytest

from stm_solver.benchmarks import (
    active_cases,
    generate_frame_candidate_benchmark,
    load_benchmark_suite,
    run_benchmark,
    run_fhwa_design_benchmark,
    run_hand_multi_panel_benchmark,
)

SUITE_PATH = Path(__file__).parents[1] / "benchmarks" / "fhwa_nhi_130126.toml"


def test_fhwa_suite_catalogs_all_four_design_examples():
    suite = load_benchmark_suite(SUITE_PATH)
    assert suite["suite_id"] == "fhwa_nhi_130126"
    assert len(suite["cases"]) == 4
    assert len(active_cases(suite)) == 3


@pytest.mark.parametrize("case", active_cases(load_benchmark_suite(SUITE_PATH)))
def test_active_fhwa_benchmarks(case):
    outcome = run_benchmark(case)
    assert outcome.passed, outcome.checks
    assert all(outcome.checks.values())


def test_reference_only_case_cannot_be_run_as_if_validated():
    suite = load_benchmark_suite(SUITE_PATH)
    case = next(case for case in suite["cases"] if case["status"] == "reference_only")
    with pytest.raises(ValueError, match="Unsupported benchmark type"):
        run_benchmark(case)


def test_example_3_candidate_generation_recovers_published_topology():
    suite = load_benchmark_suite(SUITE_PATH)
    case = next(case for case in suite["cases"] if case["id"].startswith("example_3"))
    result = generate_frame_candidate_benchmark(case)
    node_ids = {node["id"]: index for index, node in enumerate(case["nodes"])}
    expected = {
        tuple(sorted((node_ids[member["i"]], node_ids[member["j"]])))
        for member in case["members"]
    }

    assert result.candidate_count == 33
    assert {tuple(member) for member in result.truss_model.members} == expected
    assert result.equilibrium_residual < 1e-7


def test_fhwa_example_1_design_details_match_published_values():
    suite = load_benchmark_suite(SUITE_PATH)
    case = next(case for case in suite["cases"] if case["id"].startswith("example_1"))
    outcome = run_fhwa_design_benchmark(case)

    assert outcome.passed, outcome.checks
    assert all(outcome.checks.values())


def test_hand_solvable_two_panel_benchmark():
    outcome = run_hand_multi_panel_benchmark(100.0)
    assert outcome.passed, outcome.checks
    assert all(outcome.checks.values())
