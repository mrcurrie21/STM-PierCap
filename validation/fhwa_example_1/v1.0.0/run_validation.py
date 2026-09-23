"""Run the source-backed FHWA Example 1 benchmark and save its comparison report."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
sys.path.insert(0, str(ROOT))

from stm_solver.benchmarks import load_benchmark_suite, run_benchmark  # noqa: E402

suite = load_benchmark_suite(ROOT / "benchmarks" / "fhwa_nhi_130126.toml")
case = next(item for item in suite["cases"] if item["id"] == "example_1_simply_supported_deep_beam")
outcome = run_benchmark(case)
result = outcome.result
case_tolerance = float(case["force_tolerance"])

actual_reactions = []
for pile_index in range(len(case["piles"])):
    node = result.truss_model.support_node_ids[pile_index]
    actual_reactions.append(result.reactions.get(2 * node + 1, 0.0))
diagonals = []
chords = []
for (i, j), force in zip(result.truss_model.members, result.member_forces):
    delta = result.truss_model.nodes[j] - result.truss_model.nodes[i]
    if abs(delta[0]) > 1e-8 and abs(delta[1]) > 1e-8 and force < 0.0:
        diagonals.append(abs(float(force)))
    if abs(delta[1]) <= 1e-8:
        chords.append(abs(float(force)))

rows = []
for quantity, published, computed, tolerance, passed in (
    ("Left vertical reaction (kip)", case["expected_vertical_reactions"][0], actual_reactions[0], case_tolerance, outcome.checks["vertical_reactions"]),
    ("Right vertical reaction (kip)", case["expected_vertical_reactions"][1], actual_reactions[1], case_tolerance, outcome.checks["vertical_reactions"]),
    ("Primary diagonal compression (kip)", case["expected_diagonal_compression"], diagonals[0] if diagonals else None, case_tolerance, outcome.checks["diagonal_compression"]),
    ("Primary chord force (kip)", case["expected_chord_force"], chords[0] if chords else None, case_tolerance, outcome.checks["chord_forces"]),
    ("Equilibrium residual (kip)", 0.0, result.equilibrium_residual, 1e-7, outcome.checks["equilibrium"]),
):
    difference = None if computed is None else computed - published
    ratio = None if computed is None or published == 0 else computed / published
    rows.append({
        "quantity": quantity,
        "source_pages": case["source_pages"],
        "published": published,
        "computed": computed,
        "computed_over_published": ratio,
        "difference": difference,
        "tolerance": tolerance,
        "status": "PASS" if passed else "FAIL",
    })

payload = {
    "package_id": "fhwa_example_1",
    "package_version": "1.0.0",
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "repository_root": str(ROOT),
    "benchmark_case": case["id"],
    "overall_status": "PASS" if outcome.passed else "FAIL",
    "candidate_count": result.candidate_count,
    "equilibrium_residual_kip": result.equilibrium_residual,
    "checks": {key: bool(value) for key, value in outcome.checks.items()},
    "comparisons": rows,
}
(PACKAGE / "benchmark_results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

markdown = [
    "# FHWA Design Example 1 benchmark results",
    "",
    f"Overall status: **{payload['overall_status']}**",
    "",
    "This report covers the active source-backed direct-strut force/topology benchmark. FHWA Table 1-3 explicitly accepts this symmetric direct-strut alternative to the instructional two-panel left side.",
    "",
    f"- Source pages: {', '.join(map(str, case['source_pages']))}",
    f"- Candidate members: {result.candidate_count}",
    f"- Equilibrium residual: {result.equilibrium_residual:.3g} kip",
    f"- Case force tolerance: +/-{case_tolerance:g} kip",
    "",
    "| Quantity | Published | Computed | Computed / published | Difference | Tolerance | Status |",
    "|---|---:|---:|---:|---:|---:|---|",
]
def fmt(value):
    return "-" if value is None else f"{value:.4f}"


for row in rows:
    markdown.append(
        f"| {row['quantity']} | {fmt(row['published'])} | {fmt(row['computed'])} | "
        f"{fmt(row['computed_over_published'])} | {fmt(row['difference'])} | "
        f"+/-{fmt(row['tolerance'])} | {row['status']} |"
    )
markdown.extend(["", "Individual checks:", ""])
markdown.extend(f"- {name}: {'PASS' if value else 'FAIL'}" for name, value in payload["checks"].items())
markdown.append("")
(PACKAGE / "benchmark_results.md").write_text("\n".join(markdown), encoding="utf-8")
print(PACKAGE / "benchmark_results.md")
