"""Create an FHWA Example 1 copy of the unchanged production notebook."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parent
SOURCE = ROOT / "notebooks" / "pier_cap_design.ipynb"
TARGET = PACKAGE / "fhwa_example_1_production_validation.ipynb"

notebook = json.loads(SOURCE.read_text(encoding="utf-8"))

replacement = """project = {
    'name': 'FHWA Design Example 1 - Simply Supported Deep Beam',
    'designer': 'FHWA/NHI published solved example',
    'date': '09/23/2026',
    'revision': '1.0.0',
    'governing_standard': 'FHWA-NHI-13-0126 Design Example 1 / AASHTO LRFD basis',
    'units': {'length': 'in', 'force': 'kip', 'stress': 'ksi'},
}

cap = {
    'length': 324.0,
    'depth': 72.0,
    'width': 48.0,
    'top_tie_y': 69.0,
    'bottom_tie_y': 5.0,
}

materials = {
    'fc_ksi': 5.0,
    'fy_ksi': 60.0,
}

# FHWA assumptions: 2-in cover, normal-weight concrete, uncoated bars.
detailing = {
    'clear_cover': 2.0,
    'maximum_aggregate_size': 0.75,
    'lightweight_concrete': False,
    'epoxy_coated_reinforcement': False,
    'minimum_longitudinal_bar_size': 5,
    'maximum_longitudinal_bar_size': 11,
    'allow_standard_hooks': True,
}

# FHWA final reinforcement used where it maps directly to production inputs.
provided_reinforcement = {
    'bottom': {'bar_count': 16, 'bar_size': 10, 'layers': 2},
    'crack_control': {
        'vertical': {
            'steel_area_per_spacing': 1.24, 'spacing': 8.0,
            'bar_size': 5, 'legs': 4,
        },
        'horizontal': {
            'steel_area_per_spacing': 1.76, 'spacing': 12.0,
            'bar_size': 6, 'legs': 4,
        },
    },
}

# FHWA Example 1 uses the same 0.90 tension and 0.70 compression factors.
arema_phi = arema_2025_stm_resistance_factors()
code_profile = {
    'name': 'FHWA Example 1 AASHTO LRFD resistance factors',
    'phi_tie': 0.90,
    'phi_concrete': 0.70,
    'resistance_factor_status': 'SOURCE VERIFIED - FHWA-NHI-13-0126 Example 1',
}

output_options = {
    'write_files': True,
    'directory': repo_root / 'validation' / 'fhwa_example_1' / 'v1.0.0' / 'output',
    'write_excel': False,
}

# Final 14-in bearing plates follow the correction in FHWA Design Step 8.
piles = [
    {'id': 'R1', 'x': 12.0, 'y': 0.0, 'type': 'pin', 'face_width': 14.0},
    {'id': 'R2', 'x': 312.0, 'y': 0.0, 'type': 'roller', 'face_width': 14.0},
]

load_components = {
    'FHWA_STRENGTH': [
        {'id': 'L1', 'x': 120.0, 'y': 72.0, 'Px': 0.0, 'Py': -600.0},
        {'id': 'L2', 'x': 204.0, 'y': 72.0, 'Px': 0.0, 'Py': -600.0},
    ],
}

load_face_widths = {'L1': 14.0, 'L2': 14.0}
load_combinations = {'FHWA_STRENGTH': {'FHWA_STRENGTH': 1.0}}

generation = {
    'min_angle': 25.0,
    'max_angle': 75.0,
}
"""

input_cell = next(
    cell for cell in notebook["cells"]
    if cell.get("cell_type") == "code"
    and "project = {" in "".join(cell.get("source", []))
    and "load_components = {" in "".join(cell.get("source", []))
)
input_cell["source"] = replacement.splitlines(keepends=True)
input_cell["outputs"] = []
input_cell["execution_count"] = None

scope = {
    "cell_type": "markdown",
    "id": "fhwa-validation-scope",
    "metadata": {},
    "source": [
        "## FHWA Example 1 validation run\n",
        "\n",
        "Only the production notebook input cell is replaced. All other production "
        "code cells are unchanged. The input follows FHWA Figures 1-1 and 1-8 and "
        "uses the final 14-in bearing plates from Design Step 8. The optimizer is "
        "allowed to select the symmetric direct-strut model, which FHWA Table 1-3 "
        "identifies as a valid and more efficient alternative to the example's "
        "instructional two-panel model on the left side.\n",
    ],
}
notebook["cells"].insert(2, scope)
notebook["metadata"]["fhwa_validation"] = {
    "package_id": "fhwa_example_1",
    "package_version": "1.0.0",
    "source": "sources/FHWA-NHI-13-0126_Strut-and-Tie_Modeling_Design_Examples.pdf",
    "production_code_cells_unchanged": True,
}

TARGET.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(TARGET)
