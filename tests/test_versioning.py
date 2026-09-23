"""Tests for reproducible calculation artifact metadata."""

from stm_solver.versioning import build_calculation_metadata


def test_calculation_metadata_is_stable_for_equivalent_payloads():
    first = build_calculation_metadata(
        inputs={"b": 2, "a": 1}, results={"rows": [{"x": 3}]},
        project_revision="B", generated_at="2026-09-23T12:00:00+00:00",
    )
    second = build_calculation_metadata(
        inputs={"a": 1, "b": 2}, results={"rows": [{"x": 3}]},
        project_revision="B", generated_at="2026-09-23T12:00:00+00:00",
    )

    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["result_fingerprint"] == second["result_fingerprint"]
    assert first["project_revision"] == "B"
    assert first["notebook_template_version"]
    assert first["html_report_version"]
