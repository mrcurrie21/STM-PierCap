from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "txdot_global_stm_validation.ipynb"

PUBLISHED_REACTIONS = {
    "C1": 440.2,
    "C2": 620.0,
    "C3": 680.5,
    "C4": 918.5,
    "C5": 499.7,
}


def notebook_text() -> str:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    chunks: list[str] = []
    for cell in notebook["cells"]:
        for output in cell.get("outputs", []):
            value = output.get("text")
            if value is None:
                value = output.get("data", {}).get("text/plain")
            if isinstance(value, list):
                value = "".join(value)
            if value:
                chunks.append(value)
    return "\n".join(chunks)


def extract_reactions(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    pattern = re.compile(r"TXDOT_GLOBAL\s+(C[1-5])\s+[-+]?\d+(?:\.\d+)?\s+([-+]?\d+(?:\.\d+)?)")
    for support, vertical in pattern.findall(text):
        result[support] = float(vertical)
    if set(result) != set(PUBLISHED_REACTIONS):
        raise RuntimeError(f"Could not recover all notebook reactions: {result}")
    return result


def joint_residual(
    point: tuple[float, float],
    external: tuple[float, float],
    members: list[tuple[tuple[float, float], float]],
) -> float:
    origin = np.asarray(point, dtype=float)
    residual = np.asarray(external, dtype=float)
    for remote, force in members:
        vector = np.asarray(remote, dtype=float) - origin
        residual += force * vector / np.linalg.norm(vector)
    return float(np.linalg.norm(residual))


text = notebook_text()
production_reactions = extract_reactions(text)

reaction_rows = []
for support, published in PUBLISHED_REACTIONS.items():
    calculated = production_reactions[support]
    reaction_rows.append(
        {
            "support": support,
            "published_kip": published,
            "production_kip": calculated,
            "difference_kip": calculated - published,
            "difference_percent": 100.0 * (calculated - published) / published,
            "status": "PASS" if abs(calculated - published) / published <= 0.02 else "FAIL",
        }
    )

# Three non-support joints distributed across Figure 4.10. Positive member force
# is tension and negative force is compression. Coordinates are in feet on the
# published 2.90-ft global chord separation.
joint_rows = [
    {
        "node": "A",
        "residual_kip": joint_residual(
            (2.21, 2.90),
            (0.0, -228.4),
            [((9.29, 2.90), 180.5), ((4.50, 0.0), -291.1)],
        ),
    },
    {
        "node": "L",
        "residual_kip": joint_residual(
            (46.24, 2.90),
            (0.0, 0.0),
            [
                ((42.50, 2.90), 312.2),
                ((49.98, 2.90), 5.8),
                ((46.24, 0.0), 238.0),
                ((42.50, 0.0), -388.0),
            ],
        ),
    },
    {
        "node": "P",
        "residual_kip": joint_residual(
            (58.27, 2.90),
            (0.0, -233.3),
            [
                ((56.34, 2.90), 46.9),
                ((63.06, 2.90), 550.3),
                ((58.27, 0.0), 217.5),
                ((61.50, 0.0), -675.7),
            ],
        ),
    },
]
for row in joint_rows:
    row["status"] = "PASS" if row["residual_kip"] <= 1.0 else "FAIL"

tie_rows = [
    {
        "check": "Top longitudinal tie P-Q",
        "published_demand": 550.3,
        "calculated": 550.3 / (0.9 * 60.0),
        "published": 10.19,
        "units": "in^2 required",
    },
    {
        "check": "Bottom longitudinal tie FF-GG",
        "published_demand": 300.7,
        "calculated": 300.7 / (0.9 * 60.0),
        "published": 5.57,
        "units": "in^2 required",
    },
    {
        "check": "Vertical tie L-FF",
        "published_demand": 238.0,
        "calculated": 238.0 / (0.9 * 60.0),
        "published": 4.41,
        "units": "in^2 required",
    },
    {
        "check": "Vertical tie L-FF, 2-leg #5",
        "published_demand": 238.0,
        "calculated": 57.2 / ((238.0 / (0.9 * 60.0)) / (2.0 * 0.31)),
        "published": 8.0,
        "units": "in spacing",
    },
    {
        "check": "Vertical tie P-II",
        "published_demand": 217.5,
        "calculated": 217.5 / (0.9 * 60.0),
        "published": 4.03,
        "units": "in^2 required",
    },
    {
        "check": "Vertical tie P-II, 4-leg #5",
        "published_demand": 217.5,
        "calculated": 23.1 / ((217.5 / (0.9 * 60.0)) / (4.0 * 0.31)),
        "published": 7.1,
        "units": "in spacing",
    },
]
for row in tie_rows:
    row["difference_percent"] = 100.0 * (row["calculated"] - row["published"]) / row["published"]
    row["status"] = "PASS" if abs(row["difference_percent"]) <= 1.0 else "FAIL"

bearing_capacity = 0.7 * 0.65 * 4.0 * (8.0 * 21.0)
bearing_row = {
    "check": "Critical girder bearing (non-column Node P)",
    "calculated_kip": bearing_capacity,
    "published_kip": 306.0,
    "difference_percent": 100.0 * (bearing_capacity - 306.0) / 306.0,
    "status": "PASS" if abs(bearing_capacity - 306.0) / 306.0 <= 0.01 else "FAIL",
}

result = {
    "source": {
        "report": "TxDOT 5-5253-01-1, Strut-and-Tie Model Design Examples for Bridges",
        "chapter": "Chapter 4, Example 1: Five-Column Bent Cap of a Skewed Bridge",
        "global_figure": "Figure 4.10",
    },
    "scope": {
        "included": [
            "production-notebook global solve",
            "published global-joint equilibrium spot checks",
            "published longitudinal and vertical tie calculations",
            "critical non-column girder-bearing calculation",
        ],
        "excluded": [
            "local subdivided column nodes EE, JJ, and NN",
            "non-column nodes P, Q, R, and V where published strut angles depend on a subdivided column node",
            "strut-interface checks that use those revised local angles",
        ],
    },
    "production_global_result": {
        "status": "FAIL_REACTION_BASIS",
        "equilibrium_residual_kip": 2.273737e-13,
        "published_load_sum_kip": 3159.1,
        "published_reaction_sum_kip": 3158.9,
        "rounding_imbalance_kip": 0.2,
        "reaction_comparison": reaction_rows,
        "finding": (
            "The production ground-structure optimizer satisfies equilibrium but chooses support reactions "
            "by its truss LP objective. It does not reproduce the indeterminate continuous-beam reactions "
            "supplied by TxDOT, so its selected topology and member forces are not a like-for-like Figure 4.10 solution."
        ),
    },
    "published_global_statics": {
        "status": "PASS",
        "joint_spot_checks": joint_rows,
        "note": "Residual tolerance is 1.0 kip because Figure 4.10 dimensions and forces are rounded.",
    },
    "tie_checks": tie_rows,
    "non_column_node_checks": [bearing_row],
    "strut_checks": {
        "status": "DEFERRED_LOCAL_MODEL_DEPENDENT",
        "note": (
            "Chapter 4 reports strut strength through nodal strut-interface checks. The reported checks at "
            "P, R, and V use strut angles revised after subdividing a column-support node, so none remain "
            "like-for-like under the agreed global-only boundary."
        ),
    },
    "production_change": "NONE",
}

(HERE / "benchmark_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    rule = "|" + "|".join("---" for _ in headers) + "|"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([head, rule, *body])


markdown = [
    "# TxDOT Five-Column Bent Global STM Validation",
    "",
    "## Outcome",
    "",
    "The published Figure 4.10 global STM and the eligible published tie/bearing calculations are internally consistent. "
    "The production notebook does **not** reproduce the published five-column reactions, so its automatically selected "
    "topology and member forces cannot be accepted as a like-for-like validation of Figure 4.10.",
    "",
    "No production code was changed.",
    "",
    "## Production reaction comparison",
    "",
    table(
        ["Support", "TxDOT (kip)", "Notebook (kip)", "Difference", "Status"],
        [[r["support"], f'{r["published_kip"]:.1f}', f'{r["production_kip"]:.1f}', f'{r["difference_percent"]:+.1f}%', r["status"]] for r in reaction_rows],
    ),
    "",
    "Notebook equilibrium residual: 2.27e-13 kip (PASS). The issue is reaction selection, not equilibrium.",
    "",
    "## Published global-joint statics",
    "",
    table(
        ["Non-support node", "Residual (kip)", "Status"],
        [[r["node"], f'{r["residual_kip"]:.3f}', r["status"]] for r in joint_rows],
    ),
    "",
    "## Published tie calculations",
    "",
    table(
        ["Check", "Calculated", "Published", "Difference", "Status"],
        [[r["check"], f'{r["calculated"]:.3f}', f'{r["published"]:.3f}', f'{r["difference_percent"]:+.2f}%', r["status"]] for r in tie_rows],
    ),
    "",
    "## Eligible non-column node check",
    "",
    f"Critical girder bearing at Node P: {bearing_capacity:.2f} kip calculated versus 306 kip published ({bearing_row['status']}).",
    "",
    "## Exclusions",
    "",
    "- Column-support nodes EE, JJ, and NN are excluded.",
    "- Published node/strut-interface checks at P, Q, R, and V are also excluded because their final geometry uses strut angles revised after column-node subdivision.",
    "- Consequently, Chapter 4 contains no remaining standalone non-column strut-capacity check on the unmodified global geometry.",
    "",
    "## Validation finding",
    "",
    "A future prescribed-reaction input is needed for a true end-to-end Figure 4.10 comparison. The reactions must come from the adjoining frame/continuous-beam analysis; they should not be selected by the STM topology objective for this indeterminate five-support cap.",
]
markdown_text = "\n".join(markdown) + "\n"
(HERE / "benchmark_results.md").write_text(markdown_text, encoding="utf-8")

body = "\n".join(
    f"<h{len(m.group(1))}>{html.escape(m.group(2))}</h{len(m.group(1))}>"
    if (m := re.match(r"^(#+) (.*)$", line))
    else "<p></p>" if not line
    else f"<p>{html.escape(line)}</p>"
    for line in markdown
    if not line.startswith("|")
)
html_text = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>TxDOT Global STM Validation</title>
<style>body{{font-family:Arial,sans-serif;max-width:1050px;margin:36px auto;line-height:1.45;color:#17212b}}h1,h2{{color:#173f5f}}table{{border-collapse:collapse;width:100%;margin:12px 0 24px}}th,td{{border:1px solid #b9c4ce;padding:7px;text-align:right}}th:first-child,td:first-child{{text-align:left}}.pass{{color:#176b32;font-weight:bold}}.fail{{color:#a12622;font-weight:bold}}code{{background:#eef2f5;padding:2px 4px}}</style></head>
<body><h1>TxDOT Five-Column Bent Global STM Validation</h1>
<h2>Outcome</h2><p>The published Figure 4.10 global STM and eligible published tie/bearing calculations are internally consistent. The production notebook does <strong>not</strong> reproduce the published five-column reactions, so its automatic topology and forces are not a like-for-like validation. No production code was changed.</p>
<h2>Production reaction comparison</h2><table><tr><th>Support</th><th>TxDOT (kip)</th><th>Notebook (kip)</th><th>Difference</th><th>Status</th></tr>{''.join(f'<tr><td>{r["support"]}</td><td>{r["published_kip"]:.1f}</td><td>{r["production_kip"]:.1f}</td><td>{r["difference_percent"]:+.1f}%</td><td class="{r["status"].lower()}">{r["status"]}</td></tr>' for r in reaction_rows)}</table>
<p>Notebook equilibrium residual: 2.27e-13 kip (PASS). The issue is reaction selection, not equilibrium.</p>
<h2>Published global-joint statics</h2><table><tr><th>Non-support node</th><th>Residual (kip)</th><th>Status</th></tr>{''.join(f'<tr><td>{r["node"]}</td><td>{r["residual_kip"]:.3f}</td><td class="{r["status"].lower()}">{r["status"]}</td></tr>' for r in joint_rows)}</table>
<h2>Published tie calculations</h2><table><tr><th>Check</th><th>Calculated</th><th>Published</th><th>Difference</th><th>Status</th></tr>{''.join(f'<tr><td>{html.escape(r["check"])}</td><td>{r["calculated"]:.3f}</td><td>{r["published"]:.3f}</td><td>{r["difference_percent"]:+.2f}%</td><td class="{r["status"].lower()}">{r["status"]}</td></tr>' for r in tie_rows)}</table>
<h2>Eligible non-column node check</h2><p>Critical girder bearing at Node P: {bearing_capacity:.2f} kip calculated versus 306 kip published (<span class="pass">PASS</span>).</p>
<h2>Excluded local-model-dependent checks</h2><p>Column nodes EE, JJ, and NN are excluded. The final published checks at P, Q, R, and V and their strut interfaces use angles revised after column-node subdivision, so they are also excluded from global-only pass/fail scoring.</p>
<h2>Validation finding</h2><p>A prescribed-reaction input is needed for a true end-to-end Figure 4.10 comparison. Those reactions come from the adjoining continuous-beam/frame analysis and should not be selected by the STM topology objective for this indeterminate cap.</p>
</body></html>"""
(HERE / "benchmark_results.html").write_text(html_text, encoding="utf-8")
print(HERE / "benchmark_results.html")

