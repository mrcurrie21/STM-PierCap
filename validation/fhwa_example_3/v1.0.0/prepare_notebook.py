from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRODUCTION = ROOT / "notebooks" / "pier_cap_design.ipynb"
VALIDATION = Path(__file__).with_name("fhwa_example_3_production_validation.ipynb")


def indent(source: str) -> str:
    return "if run_design_checks:\n" + "\n".join(
        ("    " + line) if line else "" for line in source.splitlines()
    ) + "\nelse:\n    print('Frame-boundary mode: bearing, anchorage, and member-capacity detailing checks are outside this validation scope.')\n"


notebook = json.loads(PRODUCTION.read_text(encoding="utf-8"))
cells = notebook["cells"]

imports = "".join(cells[2]["source"])
imports = imports.replace(
    "from stm_solver.ground_structure import find_member_crossings, optimize_pier_cap_load_cases",
    "from stm_solver.ground_structure import (\n    find_member_crossings, optimize_frame_boundary_load_cases,\n    optimize_pier_cap_load_cases,\n)",
)
cells[2]["source"] = imports.splitlines(keepends=True)

inputs = "".join(cells[4]["source"])
if "analysis_mode = 'pier_cap'" not in inputs:
    inputs += """

# Analysis mode. The default pile-supported workflow is unchanged. Use
# 'frame_boundary' only when reviewed adjoining-region interface forces are
# available; see frame_model below for the required input schema.
analysis_mode = 'pier_cap'
frame_model = None
"""
cells[4]["source"] = inputs.splitlines(keepends=True)

cells[6]["source"] = """run_design_checks = analysis_mode == 'pier_cap'
if run_design_checks:
    geometry = PierCapGeometry(
        depth=cap['depth'], top_tie_y=cap['top_tie_y'],
        bottom_tie_y=cap['bottom_tie_y'], length=cap['length'], width=cap['width'],
    )
    supports = tuple(
        FoundationSupport(
            pile['id'], pile['x'], pile['y'], pile['face_width'],
            restraint=pile['type'], foundation_type=pile.get('foundation_type', 'pile'),
        )
        for pile in piles
    )
    components = tuple(
        LoadComponent(name, tuple(
            LoadPointForce(
                load['id'], load['x'], load['y'], load['Py'], px=load.get('Px', 0.0),
            )
            for load in loads
        ))
        for name, loads in load_components.items()
    )
    combinations = tuple(LoadCombination(name, factors) for name, factors in load_combinations.items())
    load_set = PierCapLoadSet(components, combinations, load_face_widths)
    load_set.validate_envelope(geometry)
    assembled_loads = load_set.assemble_all()
    models = {name: PierCapModel(geometry, loads, supports, metadata=project) for name, loads in assembled_loads.items()}
    combination_loads = {name: [load.to_solver_dict() for load in loads] for name, loads in assembled_loads.items()}
    piles = [support.to_solver_dict() for support in supports]
    print(f"Validated {len(supports)} supports, {len(components)} load components, and {len(models)} combinations.")
else:
    if frame_model is None:
        raise ValueError("frame_model is required when analysis_mode='frame_boundary'")
    frame_nodes = frame_model['top_nodes'] + frame_model['lower_nodes'] + frame_model['boundary_nodes']
    frame_node_lookup = {node['id']: node for node in frame_nodes}
    combination_loads = {
        name: [dict(load, id=load['node'], x=frame_node_lookup[load['node']]['x'], y=frame_node_lookup[load['node']]['y']) for load in loads]
        for name, loads in frame_model['load_cases'].items()
    }
    piles = [dict(node, type='fixed', face_width=0.0) for node in frame_model['boundary_nodes']]
    models = {}
    print(f"Validated {len(frame_model['boundary_nodes'])} frame-boundary nodes and {len(combination_loads)} load case(s).")
for name, loads in combination_loads.items():
    resultant = np.sum([[load.get('Px', 0.0), load.get('Py', 0.0)] for load in loads], axis=0)
    print(f"  {name:<30} Fx={resultant[0]:9.1f} kip  Fy={resultant[1]:9.1f} kip")
""".splitlines(keepends=True)

cells[8]["source"] = """if run_design_checks:
    common_analysis = optimize_pier_cap_load_cases(
        combination_loads, piles,
        top_tie_y=cap['top_tie_y'], bottom_tie_y=cap['bottom_tie_y'],
        min_angle=generation['min_angle'], max_angle=generation['max_angle'],
    )
else:
    common_analysis = optimize_frame_boundary_load_cases(
        frame_model['top_nodes'], frame_model['lower_nodes'], frame_model['boundary_nodes'],
        frame_model['load_cases'],
        boundary_member_targets=frame_model.get('boundary_member_targets'),
        target_relative_tolerance=frame_model.get('target_relative_tolerance', 0.0),
        min_angle=generation['min_angle'], max_angle=generation['max_angle'],
        force_tolerance=generation.get('force_tolerance', 1e-6),
    )
results = common_analysis.case_results

summary_records = []
for name, result in results.items():
    summary_records.append({
        'combination': name, 'candidate_count': result.candidate_count,
        'selected_count': len(result.member_forces),
        'equilibrium_residual_kip': result.equilibrium_residual,
    })
    assert result.equilibrium_residual < 1e-7
result_tables = {name: records_to_dataframes(ground_structure_records(result)) for name, result in results.items()}
summary_table = records_to_dataframes({'summary': summary_records})['summary']
common_tables = records_to_dataframes(multi_load_ground_structure_records(common_analysis))
display(summary_table)
print(f'Common candidates: {common_analysis.initial_candidate_count} generated, {len(common_analysis.members)} retained after {common_analysis.pruning_iterations} pruning iteration(s).')
if common_analysis.force_reversals:
    display(common_tables['force_reversals'])
else:
    print('Force-reversal check: PASS - no common member changes between tension and compression.')
""".splitlines(keepends=True)

cells[10]["source"] = """if run_design_checks:
    print(f"{'combination':<30} {'support':<10} {'Rx (kip)':>12} {'Ry (kip)':>12}")
    print('-' * 68)
    inactive_supports = []
    for name, result in results.items():
        for pile_index, pile in enumerate(piles):
            node = result.truss_model.support_node_ids[pile_index]
            rx = result.reactions.get(2 * node, 0.0)
            ry = result.reactions.get(2 * node + 1, 0.0)
            print(f"{name:<30} {pile['id']:<10} {rx:12.1f} {ry:12.1f}")
            if abs(rx) < 1e-6 and abs(ry) < 1e-6:
                inactive_supports.append((name, pile['id']))
else:
    print(f"{'combination':<30} {'boundary':<10} {'Rx (kip)':>12} {'Ry (kip)':>12}")
    print('-' * 68)
    offset = len(frame_model['top_nodes']) + len(frame_model['lower_nodes'])
    for name, result in results.items():
        for boundary_index, boundary in enumerate(frame_model['boundary_nodes']):
            node = offset + boundary_index
            print(f"{name:<30} {boundary['id']:<10} {result.reactions.get(2*node, 0.0):12.1f} {result.reactions.get(2*node+1, 0.0):12.1f}")
""".splitlines(keepends=True)

plot = "".join(cells[12]["source"])
plot = plot.replace("    ax.scatter([pile['x'] for pile in piles], [pile['y'] for pile in piles],\n               marker='^', s=75, color='black', label='pile/support')", "    ax.scatter([pile['x'] for pile in piles], [pile['y'] for pile in piles],\n               marker='^', s=75, color='black', label=('pile/support' if run_design_checks else 'frame boundary'))")
cells[12]["source"] = plot.splitlines(keepends=True)

for index in range(15, 23):
    cells[index]["source"] = indent("".join(cells[index]["source"])).splitlines(keepends=True)

PRODUCTION.write_text(json.dumps(notebook, indent=1), encoding="utf-8")

validation = copy.deepcopy(notebook)
validation_inputs = """project = {
    'name': 'FHWA NHI-13-0126 Example 3 - Production Notebook Validation',
    'designer': 'Validation benchmark', 'date': '09/23/2026', 'revision': '1',
    'governing_standard': 'FHWA-NHI-13-012, Design Example 3',
    'units': {'length': 'ft', 'force': 'kip', 'stress': 'ksi'},
}
cap = {'length': 47.5, 'depth': 5.12, 'width': 4.0, 'top_tie_y': 5.62, 'bottom_tie_y': 0.50}
materials = {'fc_ksi': 4.0, 'fy_ksi': 60.0}
detailing = {'clear_cover': 2.0, 'maximum_aggregate_size': 0.75, 'lightweight_concrete': False, 'epoxy_coated_reinforcement': False, 'minimum_longitudinal_bar_size': 5, 'maximum_longitudinal_bar_size': 11, 'allow_standard_hooks': True}
provided_reinforcement = None
arema_phi = arema_2025_stm_resistance_factors()
code_profile = {'name': 'FHWA Example 3 force-flow validation only', 'phi_tie': arema_phi['reinforced_concrete_tension'], 'phi_concrete': arema_phi['compression'], 'resistance_factor_status': 'Not used in force-flow validation'}
output_options = {'write_files': False, 'directory': repo_root / 'validation' / 'fhwa_example_3' / 'v1.0.0' / 'output', 'write_excel': False}
piles = []
load_components = {}
load_face_widths = {}
load_combinations = {}
generation = {'min_angle': 25.0, 'max_angle': 90.0, 'force_tolerance': 0.001}
analysis_mode = 'frame_boundary'
frame_model = {
    'top_nodes': [
        {'id': 'A', 'x': 0.57, 'y': 5.62}, {'id': 'B', 'x': 12.83, 'y': 5.62}, {'id': 'C', 'x': 21.45, 'y': 5.62},
        {'id': 'D', 'x': 29.87, 'y': 5.62}, {'id': 'E', 'x': 38.29, 'y': 5.62}, {'id': 'F', 'x': 46.93, 'y': 5.62},
    ],
    'lower_nodes': [
        {'id': 'G', 'x': 4.21, 'y': 0.50, 'connect_top_indices': [0, 1]}, {'id': 'H', 'x': 12.83, 'y': 0.50, 'connect_top_indices': [1, 2]},
        {'id': 'I', 'x': 21.45, 'y': 0.50, 'connect_top_indices': [2]}, {'id': 'J', 'x': 29.87, 'y': 0.50, 'connect_top_indices': [2, 3]},
        {'id': 'K', 'x': 38.29, 'y': 0.50, 'connect_top_indices': [3, 4]}, {'id': 'L', 'x': 43.39, 'y': 0.50, 'connect_top_indices': [4, 5]},
    ],
    'boundary_nodes': [
        {'id': 'A_prime', 'x': 0.57, 'y': -5.0, 'connect_group': 'top', 'connect_index': 0, 'additional_connections': [{'connect_group': 'lower', 'connect_index': 0}], 'connect_boundary_indices': [1]},
        {'id': 'G_prime', 'x': 4.21, 'y': -5.0, 'connect_group': 'lower', 'connect_index': 0},
        {'id': 'L_prime', 'x': 43.39, 'y': -5.0, 'connect_group': 'lower', 'connect_index': 5, 'connect_boundary_indices': [3]},
        {'id': 'F_prime', 'x': 46.93, 'y': -5.0, 'connect_group': 'top', 'connect_index': 5, 'additional_connections': [{'connect_group': 'lower', 'connect_index': 5}]},
    ],
    'load_cases': {'FHWA_EXAMPLE_3': [
        {'node': 'B', 'Py': -16.2}, {'node': 'C', 'Py': -20.4}, {'node': 'D', 'Py': -20.7}, {'node': 'E', 'Py': -16.5},
        {'node': 'G', 'Py': -32.2}, {'node': 'H', 'Py': -16.2}, {'node': 'I', 'Py': -517.4}, {'node': 'J', 'Py': -438.8},
        {'node': 'K', 'Py': -449.3}, {'node': 'L', 'Py': -26.0},
    ]},
    'boundary_member_targets': {'FHWA_EXAMPLE_3': [
        {'i': 'A', 'j': 'A_prime', 'force': 653.9}, {'i': 'A_prime', 'j': 'G', 'force': -457.3},
        {'i': 'A_prime', 'j': 'G_prime', 'force': 268.9}, {'i': 'G', 'j': 'G_prime', 'force': -864.7},
        {'i': 'L', 'j': 'L_prime', 'force': -1213.8}, {'i': 'L_prime', 'j': 'F_prime', 'force': 268.9},
        {'i': 'F', 'j': 'F_prime', 'force': 620.8}, {'i': 'L', 'j': 'F_prime', 'force': -465.6},
    ]},
    'target_relative_tolerance': 0.03,
}
"""
validation["cells"][4]["source"] = validation_inputs.splitlines(keepends=True)
for cell in validation["cells"]:
    if cell["cell_type"] == "code":
        cell["outputs"] = []
        cell["execution_count"] = None
VALIDATION.write_text(json.dumps(validation, indent=1), encoding="utf-8")
print(PRODUCTION)
print(VALIDATION)
