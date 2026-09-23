"""Tabular adapters for review, notebooks, and file export."""

import csv
import json
import math
import re
from dataclasses import asdict
from pathlib import Path


def ground_structure_records(result):
    """Convert a ground-structure result to normalized table records."""
    truss = result.truss_model
    return {
        "nodes": [
            {"node_id": index, "x": float(x), "y": float(y)}
            for index, (x, y) in enumerate(truss.nodes)
        ],
        "members": [
            {
                "member_id": index, "node_i": int(i), "node_j": int(j),
                "force": float(force), "member_type": truss.member_types[index],
            }
            for index, ((i, j), force) in enumerate(zip(truss.members, result.member_forces))
        ],
        "reactions": [
            {
                "dof": int(dof), "node_id": int(dof // 2),
                "direction": "x" if dof % 2 == 0 else "y",
                "reaction": float(reaction),
            }
            for dof, reaction in sorted(result.reactions.items())
        ],
        "external_faces": [
            {
                "kind": face.kind, "source_index": face.source_index,
                "node_id": face.node_id, "center_x": face.center[0],
                "center_y": face.center[1], "start_x": face.start[0],
                "start_y": face.start[1], "end_x": face.end[0],
                "end_y": face.end[1], "width": face.width,
                "inward_normal_x": face.inward_normal[0],
                "inward_normal_y": face.inward_normal[1],
            }
            for face in truss.external_faces
        ],
    }


def multi_load_ground_structure_records(result):
    """Normalize common-candidate provenance and force reversals."""
    force_rows = []
    for combination, case in result.case_results.items():
        local_ids = {
            int(common_index): local_id
            for local_id, common_index in enumerate(case.selected_candidate_indices)
        }
        for common_index, (candidate_id, (node_i, node_j), force) in enumerate(zip(
            result.common_candidate_ids, result.members, case.candidate_forces
        )):
            force_rows.append({
                "combination": combination,
                "member_id": local_ids.get(common_index),
                "candidate_id": int(candidate_id),
                "node_i": int(node_i),
                "node_j": int(node_j),
                "force": float(force),
                "force_type": (
                    "tie" if force > 0.0 else "strut" if force < 0.0 else "inactive"
                ),
            })
    return {
        "candidate_provenance": [asdict(item) for item in result.candidate_records],
        "common_member_forces": force_rows,
        "force_reversals": [asdict(item) for item in result.force_reversals],
    }


def pier_cap_analysis_records(
    common_result, *, external_nodal_checks=None, interior_nodal_checks=None,
    strut_checks=None, tie_checks=(), tie_layouts=(), anchorage=(),
    cage_reviews=(), crack_control=(),
):
    """Assemble the normalized calculation tables for one pier-cap analysis."""
    tables = multi_load_ground_structure_records(common_result)
    tables["nodes"] = [
        {"node_id": index, "x": float(point[0]), "y": float(point[1])}
        for index, point in enumerate(common_result.nodes)
    ]
    reaction_rows = []
    quality_rows = []
    for combination, result in common_result.case_results.items():
        for dof, reaction in sorted(result.reactions.items()):
            reaction_rows.append({
                "combination": combination, "dof": int(dof),
                "node_id": int(dof // 2),
                "direction": "x" if dof % 2 == 0 else "y",
                "reaction": float(reaction),
            })
        degrees = [0] * len(result.truss_model.nodes)
        total_length = 0.0
        force_weighted_length = 0.0
        for (node_i, node_j), force in zip(
            result.truss_model.members, result.member_forces
        ):
            degrees[int(node_i)] += 1
            degrees[int(node_j)] += 1
            point_i = result.truss_model.nodes[node_i]
            point_j = result.truss_model.nodes[node_j]
            length = math.hypot(
                float(point_j[0] - point_i[0]), float(point_j[1] - point_i[1])
            )
            total_length += length
            force_weighted_length += abs(float(force)) * length
        quality_rows.append({
            "combination": combination,
            "selected_member_count": len(result.truss_model.members),
            "selected_member_length": total_length,
            "force_weighted_load_path": force_weighted_length,
            "maximum_node_degree": max(degrees, default=0),
            "equilibrium_residual": result.equilibrium_residual,
        })
    tables["reactions"] = reaction_rows
    tables["model_quality"] = quality_rows

    def tagged(mapping):
        return [
            {"combination": combination, **asdict(item)}
            for combination, items in (mapping or {}).items()
            for item in items
        ]

    tables.update({
        "external_nodal_checks": tagged(external_nodal_checks),
        "interior_nodal_checks": tagged(interior_nodal_checks),
        "strut_checks": tagged(strut_checks),
        "tie_checks": [asdict(item) for item in tie_checks],
        "tie_layouts": [asdict(item) for item in tie_layouts],
        "tie_anchorage": [asdict(item) for item in anchorage],
        "cage_reviews": [asdict(item) for item in cage_reviews],
        "crack_control": [asdict(item) for item in crack_control],
    })
    return tables


def nodal_geometry_records(
    geometries=(), tributaries=(), resolved_forces=(), group_geometries=(),
):
    """Normalize nodal-zone geometry objects into reviewable records."""
    geometry_rows = []
    for item in geometries:
        row = asdict(item)
        bearing_start, bearing_end = row.pop("bearing_face")
        interface_start, interface_end = row.pop("strut_interface")
        row.update({
            "bearing_start_x": bearing_start[0], "bearing_start_y": bearing_start[1],
            "bearing_end_x": bearing_end[0], "bearing_end_y": bearing_end[1],
            "interface_start_x": interface_start[0],
            "interface_start_y": interface_start[1],
            "interface_end_x": interface_end[0], "interface_end_y": interface_end[1],
        })
        geometry_rows.append(row)
    tributary_rows = [asdict(item) for item in tributaries]
    resolved_rows = []
    for item in resolved_forces:
        row = asdict(item)
        vector = row.pop("vector")
        row.update({"force_x": vector[0], "force_y": vector[1]})
        resolved_rows.append(row)
    group_rows = []
    for item in group_geometries:
        row = {
            "label": item.label,
            "zone_type": item.zone_type,
            "member_ids": item.member_ids,
            "node_id": item.resultant.node_id,
            "force_x": item.resultant.vector[0],
            "force_y": item.resultant.vector[1],
            "force_magnitude": item.resultant.magnitude,
            "tributary_start_x": item.tributary.start[0],
            "tributary_start_y": item.tributary.start[1],
            "tributary_end_x": item.tributary.end[0],
            "tributary_end_y": item.tributary.end[1],
            "tributary_width": item.tributary.width,
            "normal_force": item.tributary.normal_force,
            "axis_start_x": item.revised_axis.start[0],
            "axis_start_y": item.revised_axis.start[1],
            "axis_end_x": item.revised_axis.end[0],
            "axis_end_y": item.revised_axis.end[1],
            "axis_angle_degrees": item.revised_axis.angle_degrees,
            "strut_interface_width": item.strut_interface_width,
            "nodal_polygon": item.nodal_polygon,
            "interface_start_x": item.strut_interface[0][0],
            "interface_start_y": item.strut_interface[0][1],
            "interface_end_x": item.strut_interface[1][0],
            "interface_end_y": item.strut_interface[1][1],
        }
        group_rows.append(row)
    return {
        "nodal_zone_geometries": geometry_rows,
        "face_tributaries": tributary_rows,
        "resolved_nodal_forces": resolved_rows,
        "nodal_zone_groups": group_rows,
    }


def design_check_records(
    strut_checks=(), tie_checks=(), node_checks=(), nodal_face_checks=(),
):
    """Normalize design-check dataclasses into separate result tables."""
    return {
        "strut_checks": [asdict(item) for item in strut_checks],
        "tie_checks": [asdict(item) for item in tie_checks],
        "node_checks": [asdict(item) for item in node_checks],
        "nodal_face_checks": [asdict(item) for item in nodal_face_checks],
    }


def strut_width_records(profiles):
    """Normalize calculated strut end-width profiles for review and export."""
    return [asdict(profile) for profile in profiles]


def strut_shape_records(classifications):
    """Normalize strut-shape classifications for review and export."""
    return [asdict(classification) for classification in classifications]


def conservative_strut_design_records(designs):
    """Normalize simplified conservative strut design treatments."""
    return [asdict(design) for design in designs]


def crack_control_records(grids):
    """Normalize orthogonal crack-control grid results."""
    return [asdict(grid) for grid in grids]


def tie_bar_layout_records(layouts):
    """Normalize automatically selected tie-bar layouts."""
    return [asdict(layout) for layout in layouts]


def tie_anchorage_records(geometries):
    """Normalize available tie-development geometry at member ends."""
    return [asdict(geometry) for geometry in geometries]


def reinforcement_cage_review_records(reviews):
    """Normalize section-level reinforcement cage constructability screens."""
    return [asdict(review) for review in reviews]


def tension_development_records(calculations):
    """Normalize AREMA straight-bar tension development calculations."""
    return [asdict(calculation) for calculation in calculations]


def standard_hook_records(calculations):
    """Normalize AREMA standard-hook development and geometry checks."""
    return [asdict(calculation) for calculation in calculations]


def tension_lap_splice_records(calculations):
    """Normalize AREMA tension lap-splice calculations."""
    return [asdict(calculation) for calculation in calculations]


def records_to_dataframes(tables):
    """Convert record tables to pandas DataFrames when pandas is installed."""
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "Install the 'tables' or 'notebook' optional dependency for pandas"
        ) from exc
    return {name: pd.DataFrame(records) for name, records in tables.items()}


def export_csv_tables(tables, directory):
    """Write one CSV file per normalized record table."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, records in tables.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise ValueError(f"Unsafe table name for CSV export: {name!r}")
        path = directory / f"{name}.csv"
        fieldnames = list(records[0]) if records else []
        with path.open("w", newline="", encoding="utf-8") as stream:
            if fieldnames:
                writer = csv.DictWriter(stream, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)
        written[name] = path
    return written


def export_json_tables(tables, path):
    """Write all normalized record tables to one reviewable JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(tables, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return path


def export_excel_tables(tables, path):
    """Write normalized record tables to one Excel workbook."""
    frames = records_to_dataframes(tables)
    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Install the 'tables' or 'notebook' optional dependency for Excel export"
        ) from exc
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    used_names = set()
    with __import__("pandas").ExcelWriter(path, engine="openpyxl") as writer:
        for name, frame in frames.items():
            sheet_name = re.sub(r"[\\/*?:\[\]]", "_", name)[:31] or "table"
            base_name = sheet_name
            suffix = 1
            while sheet_name.lower() in used_names:
                suffix_text = f"_{suffix}"
                sheet_name = base_name[:31 - len(suffix_text)] + suffix_text
                suffix += 1
            used_names.add(sheet_name.lower())
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
    return path
