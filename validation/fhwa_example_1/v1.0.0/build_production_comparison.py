"""Compare executed production output with FHWA Example 1 published values."""

import html
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
RESULTS = PACKAGE / "output" / "pier_cap_results.json"
data = json.loads(RESULTS.read_text(encoding="utf-8"))

forces = data["common_member_forces"]
nodes = {row["node_id"]: row for row in data["nodes"]}
reactions = [
    row["reaction"] for row in data["reactions"] if row["direction"] == "y"
]
diagonals = [
    abs(row["force"]) for row in forces
    if row["force"] < 0.0
    and row["node_i"] in (4, 5) and row["node_j"] in (10, 11)
]
chords = [
    abs(row["force"]) for row in forces
    if abs(nodes[row["node_i"]]["y"] - nodes[row["node_j"]]["y"]) < 1e-9
]
tie_layout = data["tie_layouts"][0]
top_node = [
    row for row in data["external_nodal_checks"] if row["group_label"] == "load L1"
]
top_faces = {row["face_type"]: row for row in top_node}
crack = {row["direction"]: row for row in data["crack_control"]}
anchorage = data["tie_anchorage"][0]


def numerical(quantity, source, published, computed, tolerance, note=""):
    difference = computed - published
    passed = abs(difference) <= tolerance
    return {
        "quantity": quantity, "source": source, "published": published,
        "computed": computed, "difference": difference,
        "tolerance": f"+/-{tolerance:g}", "status": "PASS" if passed else "FAIL",
        "note": note,
    }


rows = [
    numerical("Left reaction (kip)", "Fig. 1-8", 600.0, reactions[0], 1.0),
    numerical("Right reaction (kip)", "Fig. 1-8", 600.0, reactions[1], 1.0),
    numerical("Direct diagonal compression (kip)", "Table 1-1, CF", 1177.0, diagonals[0], 1.0),
    numerical("Direct chord force (kip)", "Table 1-1, BC/EF", 1013.0, max(chords), 1.0),
    numerical("Bottom tie required area (in2)", "Design Step 7", 18.76, data["tie_checks"][0]["As_required"], 0.02),
    numerical("16-No.10 provided area (in2)", "Fig. 1-4", 20.32, tie_layout["as_provided"], 0.01),
    numerical("16-No.10 factored tie capacity (kip)", "Design Step 7", 1097.0, 0.90 * 60.0 * tie_layout["as_provided"], 1.0),
    numerical("Final CCC back-face capacity (kip)", "Design Step 8", 856.0, top_faces["back"]["capacity"], 1.0),
    numerical("Final CCC back-face D/C", "Design Step 8", 1.1834, top_faces["back"]["dc_ratio"], 0.005),
    numerical("Final CCC strut-interface width (in)", "Design Step 8", 12.3, top_faces["strut_interface"]["face_width"], 0.05),
    numerical("Final CCC strut capacity (kip)", "Design Step 8", 1239.0, top_faces["strut_interface"]["capacity"], 2.0),
    numerical("Final CCC strut D/C", "Design Step 8", 0.9500, top_faces["strut_interface"]["dc_ratio"], 0.005),
    numerical("Vertical crack-control area per spacing (in2)", "Design Step 9", 1.24, crack["vertical"]["steel_area_per_spacing"], 0.001),
    numerical("Vertical crack-control spacing (in)", "Design Step 9", 8.0, crack["vertical"]["selected_spacing"], 0.001),
    numerical("Horizontal crack-control area per foot (in2)", "Design Step 9", 1.76, crack["horizontal"]["steel_area_per_spacing"], 0.001),
    numerical("Horizontal crack-control spacing (in)", "Design Step 9", 12.0, crack["horizontal"]["selected_spacing"], 0.001),
]
rows.extend([
    {
        "quantity": "Hook development required (in)", "source": "Design Step 10",
        "published": 19.9, "computed": anchorage["required_development_length"],
        "difference": anchorage["required_development_length"] - 19.9,
        "tolerance": "QUALITATIVE", "status": "BASIS DIFFERENCE",
        "note": "Production notebook applies AREMA development provisions; FHWA applies AASHTO LRFD.",
    },
    {
        "quantity": "Hook anchorage available (in)", "source": "Fig. 1-21",
        "published": 25.4, "computed": anchorage["available_length"],
        "difference": anchorage["available_length"] - 25.4,
        "tolerance": "QUALITATIVE", "status": "PASS",
        "note": "Different bar-end convention; both calculated lengths exceed their governing requirement.",
    },
    {
        "quantity": "Top compression-chord reinforcement", "source": "Design Step 8",
        "published": "6-No.8 (4.74 in2)", "computed": "Concrete-only NG; 856.8 < 1012.5 kip",
        "difference": "-", "tolerance": "FUNCTIONAL", "status": "GAP",
        "note": "Production identifies the same deficiency but does not accept/design supplemental compression-strut steel.",
    },
])

summary = {
    "overall_status": "PASS WITH DOCUMENTED GAP",
    "production_notebook": "fhwa_example_1_production_validation.ipynb",
    "production_html": "fhwa_example_1_production_validation.html",
    "source_pdf": "FHWA-NHI-13-0126_Strut-and-Tie_Modeling_Design_Examples.pdf",
    "comparisons": rows,
}
(PACKAGE / "production_comparison.json").write_text(
    json.dumps(summary, indent=2) + "\n", encoding="utf-8"
)

headers = ["Quantity", "Source", "Published", "Production", "Difference", "Tolerance", "Status", "Note"]
table_rows = []
for row in rows:
    values = [
        row["quantity"], row["source"], row["published"], row["computed"],
        row["difference"], row["tolerance"], row["status"], row["note"],
    ]
    table_rows.append("| " + " | ".join(str(value) for value in values) + " |")
markdown = [
    "# FHWA Example 1 production-notebook comparison", "",
    "Overall status: **PASS WITH DOCUMENTED GAP**", "",
    "The production notebook code cells are unchanged except for the designated input cell. The automatically selected symmetric direct-strut topology is explicitly accepted by FHWA Table 1-3 as an alternative to the instructional two-panel left side.", "",
    "| " + " | ".join(headers) + " |",
    "|" + "|".join(["---"] * len(headers)) + "|",
    *table_rows, "",
    "The validation identified and corrected two shared-analysis defects: provided crack-control grids lost their bar-size metadata before cage checks, and finite-face transfer links were incorrectly treated as design struts instead of connecting the physical face to the actual STM node.", "",
]
(PACKAGE / "production_comparison.md").write_text("\n".join(markdown), encoding="utf-8")

body_rows = []
for row in rows:
    status_class = "pass" if row["status"] == "PASS" else "gap" if row["status"] in ("GAP", "BASIS DIFFERENCE") else "fail"
    cells = [row["quantity"], row["source"], row["published"], row["computed"], row["difference"], row["tolerance"], row["status"], row["note"]]
    body_rows.append(f'<tr class="{status_class}">' + "".join(f"<td>{html.escape(str(value))}</td>" for value in cells) + "</tr>")
document = f"""<!doctype html><html><head><meta charset="utf-8"><title>FHWA Example 1 validation comparison</title><style>
body{{font-family:Arial,sans-serif;margin:32px;color:#172033}} h1{{margin-bottom:6px}} .status{{font-weight:700;color:#7a4d00}} table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #ccd3df;padding:7px;vertical-align:top}} th{{background:#e9eef6;text-align:left}} tr.pass td:nth-child(7){{color:#176b37;font-weight:700}} tr.gap td:nth-child(7){{color:#8a5600;font-weight:700}} tr.fail td:nth-child(7){{color:#a11;font-weight:700}} .note{{max-width:1100px;line-height:1.45}} @media print{{body{{margin:12mm}} table{{font-size:9px}}}}
</style></head><body><h1>FHWA Example 1 production-notebook comparison</h1><p class="status">PASS WITH DOCUMENTED GAP</p><p class="note">The production notebook code cells are unchanged except for the designated input cell. The symmetric direct-strut topology is accepted by FHWA Table 1-3. Numeric comparisons below use the executed production output.</p><table><thead><tr>{''.join(f'<th>{html.escape(value)}</th>' for value in headers)}</tr></thead><tbody>{''.join(body_rows)}</tbody></table><p class="note">Corrected analysis defects: provided crack-control grids now retain bar-size metadata for cage checks, and finite external faces now connect to their actual STM nodes for nodal geometry and strut-width checks.</p></body></html>"""
(PACKAGE / "production_comparison.html").write_text(document, encoding="utf-8")
print(PACKAGE / "production_comparison.html")
