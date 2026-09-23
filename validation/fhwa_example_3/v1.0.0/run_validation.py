"""Generate the FHWA Example 3 prescribed global-STM comparison artifacts."""

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
sys.path.insert(0, str(ROOT))

from stm_solver.benchmarks import load_benchmark_suite, run_benchmark  # noqa: E402
from stm_solver.ground_structure import optimize_frame_boundary_load_cases  # noqa: E402

suite = load_benchmark_suite(ROOT / "benchmarks" / "fhwa_nhi_130126.toml")
case = next(
    item for item in suite["cases"]
    if item["id"] == "example_3_inverted_tee_straddle_bent"
)
outcome = run_benchmark(case)

node_index = {node["id"]: index for index, node in enumerate(case["nodes"])}
top_nodes = [dict(node) for node in case["nodes"] if node["role"] == "top"]
lower_nodes = [dict(node) for node in case["nodes"] if node["role"] == "lower"]
top_lookup = {node["id"]: index for index, node in enumerate(top_nodes)}
lower_lookup = {node["id"]: index for index, node in enumerate(lower_nodes)}
for lower in lower_nodes:
    lower["connect_top_indices"] = sorted({
        top_lookup[other]
        for member in case["members"]
        for other in (
            member["j"] if member["i"] == lower["id"] else
            member["i"] if member["j"] == lower["id"] else None,
        )
        if other in top_lookup
    })
boundary_nodes = []
for boundary in case["boundaries"]:
    node = case["nodes"][node_index[boundary["node"]]]
    boundary_nodes.append({
        "id": node["id"], "x": node["x"], "y": node["y"],
        "connect_group": boundary["connect_group"],
        "connect_index": boundary["connect_index"],
        "additional_connections": boundary.get("additional_connections", []),
        "connect_boundary_indices": boundary.get("connect_boundary_indices", []),
    })
targets = [{"i": member["i"], "j": member["j"], "force": member["expected_force"]}
           for member in case["members"] if member.get("fix_expected_force")]
production = optimize_frame_boundary_load_cases(
    top_nodes, lower_nodes, boundary_nodes,
    {"FHWA_EXAMPLE_3": case["nodal_loads"]},
    boundary_member_targets={"FHWA_EXAMPLE_3": targets},
    target_relative_tolerance=case["fixed_force_relative_tolerance"],
    min_angle=case["generation_min_angle"], max_angle=case["generation_max_angle"],
    force_tolerance=case["generation_force_tolerance"],
)
production_result = production.case_results["FHWA_EXAMPLE_3"]
production_lookup = {
    tuple(sorted(pair)): force
    for pair, force in zip(
        production_result.truss_model.members.tolist(), production_result.member_forces
    )
}
member_rows = []
for published in case["members"]:
    pair = tuple(sorted((node_index[published["i"]], node_index[published["j"]])))
    computed = float(production_lookup[pair])
    expected = float(published["expected_force"])
    relative_error = abs(computed - expected) / max(abs(expected), 1.0)
    tolerance = float(case["relative_force_tolerance"])
    if published.get("fix_expected_force"):
        tolerance = float(case["fixed_force_relative_tolerance"])
    member_rows.append({
        "member": published["id"],
        "i": published["i"],
        "j": published["j"],
        "published_force_kip": expected,
        "computed_force_kip": computed,
        "difference_kip": computed - expected,
        "relative_error": relative_error,
        "tolerance": tolerance,
        "status": "PASS" if relative_error <= tolerance + 1e-12 else "FAIL",
    })

reference = {
    key: value for key, value in case.items()
    if key not in {"status"}
}
(PACKAGE / "published_reference.json").write_text(
    json.dumps(reference, indent=2) + "\n", encoding="utf-8"
)
payload = {
    "package_id": "fhwa_example_3",
    "package_version": "1.0.0",
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "case_id": case["id"],
    "overall_status": "PASS" if outcome.passed and all(row["status"] == "PASS" for row in member_rows) else "FAIL",
    "equilibrium_residual_kip": production_result.equilibrium_residual,
    "checks": {**{key: bool(value) for key, value in outcome.checks.items()}, "production_notebook_solver_path": all(row["status"] == "PASS" for row in member_rows)},
    "members": member_rows,
    "node_index": node_index,
}
(PACKAGE / "benchmark_results.json").write_text(
    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
)

headers = ["Member", "Published (kip)", "Computed (kip)", "Difference (kip)", "Relative error", "Tolerance", "Status"]
markdown = [
    "# FHWA Design Example 3 global-STM benchmark", "",
    f"Overall status: **{payload['overall_status']}**", "",
    "These forces are from the optional frame-boundary solver path called by the production notebook.", "",
    f"- Equilibrium residual: {production_result.equilibrium_residual:.3g} kip", "",
    "| " + " | ".join(headers) + " |",
    "|" + "|".join(["---"] * len(headers)) + "|",
]
for row in member_rows:
    markdown.append(
        f"| {row['member']} | {row['published_force_kip']:.1f} | "
        f"{row['computed_force_kip']:.1f} | {row['difference_kip']:.1f} | "
        f"{row['relative_error']:.3%} | {row['tolerance']:.1%} | {row['status']} |"
    )
markdown.append("")
(PACKAGE / "benchmark_results.md").write_text("\n".join(markdown), encoding="utf-8")

body_rows = []
for row in member_rows:
    values = [
        row["member"], f"{row['published_force_kip']:.1f}",
        f"{row['computed_force_kip']:.1f}", f"{row['difference_kip']:.1f}",
        f"{row['relative_error']:.3%}", f"{row['tolerance']:.1%}", row["status"],
    ]
    body_rows.append(
        '<tr class="pass">' + "".join(
            f"<td>{html.escape(value)}</td>" for value in values
        ) + "</tr>"
    )
document = f"""<!doctype html><html><head><meta charset="utf-8"><title>FHWA Example 3 production validation</title><style>
body{{font-family:Arial,sans-serif;margin:32px;color:#172033}} table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #ccd3df;padding:7px}} th{{background:#e9eef6;text-align:left}} td:nth-child(n+2):nth-child(-n+6){{text-align:right}} tr.pass td:last-child{{color:#176b37;font-weight:700}} .status{{font-weight:700;color:#176b37}} .note{{line-height:1.45;max-width:1000px}}</style></head><body><h1>FHWA Design Example 3 production validation</h1><p class="status">{payload['overall_status']}</p><p class="note">The executed production notebook uses its optional frame-boundary mode. The comparison below is generated from the same shared production solver path and the frozen FHWA reference.</p><p>Equilibrium residual: {production_result.equilibrium_residual:.3g} kip</p><table><thead><tr>{''.join(f'<th>{html.escape(value)}</th>' for value in headers)}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></body></html>"""
(PACKAGE / "benchmark_results.html").write_text(document, encoding="utf-8")
print(PACKAGE / "benchmark_results.html")
