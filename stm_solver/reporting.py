"""Engineering calculation reports for pier-cap STM analyses."""

from html import escape
from pathlib import Path


def _maximum_dc(mapping):
    return max(
        (item.dc_ratio for items in mapping.values() for item in items), default=0.0
    )


def build_pier_cap_calculation_report(
    *, project, cap, materials, detailing, code_profile, common_analysis,
    tie_layouts, anchorage, cage_reviews, strut_checks,
    external_nodal_checks, interior_nodal_checks,
    metadata=None,
):
    """Return a Markdown calculation summary from completed analysis objects."""
    metadata = metadata or {}
    reversal_status = (
        f"{len(common_analysis.force_reversals)} reversal(s), designed for both signs"
        if common_analysis.force_reversals else "none"
    )
    lines = [
        f"# {project.get('name', 'Pier-Cap STM')} - Calculation Summary", "",
        f"- Project revision: {metadata.get('project_revision', 'not assigned')}",
        f"- Tool / notebook / report versions: {metadata.get('tool_version', 'n/a')} / "
        f"{metadata.get('notebook_template_version', 'n/a')} / "
        f"{metadata.get('html_report_version', 'n/a')}",
        f"- Result fingerprint: {metadata.get('result_fingerprint', 'n/a')}", "",
        "## Inputs and visible defaults", "",
        f"- Geometry: {cap['length']} in long x {cap['depth']} in deep x {cap['width']} in wide",
        f"- Materials: f'c = {materials['fc_ksi']} ksi; fy = {materials['fy_ksi']} ksi",
        f"- Clear cover: {detailing['clear_cover']} in",
        f"- Maximum aggregate size: {detailing['maximum_aggregate_size']} in",
        f"- Code profile: {code_profile['name']}",
        f"- Resistance-factor status: {code_profile['resistance_factor_status']}", "",
        "## Analysis model", "",
        f"- Common candidates: {common_analysis.initial_candidate_count} generated; {len(common_analysis.members)} retained",
        f"- Load combinations: {', '.join(common_analysis.case_results)}",
        f"- Force reversals: {reversal_status}", "", "## Reinforcement", "",
    ]
    for layer, layout in tie_layouts.items():
        lines.append(
            f"- {layer}: {layout.bar_count}-#{layout.bar_size}, "
            f"As = {layout.as_provided:.2f} in^2, {layout.layers} layer(s)"
        )
    lines.extend(["", "### Anchorage", ""])
    for item in anchorage:
        lines.append(
            f"- {item.layer}, {item.end}: {item.available_length:.2f} in available / "
            f"{item.required_development_length:.2f} in required, {item.anchorage_type}, {item.status}"
        )
    lines.extend([
        "", "## Governing checks", "",
        f"- Maximum strut D/C: {_maximum_dc(strut_checks):.3f}",
        f"- Maximum external nodal-face D/C: {_maximum_dc(external_nodal_checks):.3f}",
        f"- Maximum interior nodal-face D/C: {_maximum_dc(interior_nodal_checks):.3f}",
        f"- Section-level cage checks: {'OK' if all(item.status == 'OK' for item in cage_reviews) else 'NG'}",
        "", "## Scope", "",
        "This is a two-dimensional STM analysis. Final three-dimensional bar positioning, drawings, foundation design, and project load development are outside its scope.",
    ])
    return "\n".join(lines) + "\n"


def _fmt(value, digits=3):
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return escape(str(value))


def _force_flow_svg(common_analysis, case_name, cap):
    result = common_analysis.case_results[case_name]
    nodes, members, forces = (
        result.truss_model.nodes, result.truss_model.members, result.member_forces
    )
    pad, width, height = 34.0, 900.0, 210.0
    sx = (width - 2 * pad) / float(cap["length"])
    sy = (height - 2 * pad) / float(cap["depth"])

    def point(node):
        return pad + float(node[0]) * sx, height - pad - float(node[1]) * sy

    maximum = max((abs(float(force)) for force in forces), default=1.0) or 1.0
    lines = [
        f'<svg class="force-flow" viewBox="0 0 {width:g} {height:g}" role="img" aria-label="Strut-and-tie force-flow diagram">',
        f'<rect class="cap" x="{pad:g}" y="{pad:g}" width="{float(cap["length"]) * sx:g}" height="{float(cap["depth"]) * sy:g}" rx="3"/>',
    ]
    force_labels = []
    for member_id, ((node_i, node_j), force) in enumerate(zip(members, forces)):
        x1, y1 = point(nodes[int(node_i)])
        x2, y2 = point(nodes[int(node_j)])
        force = float(force)
        kind = "tie" if force > 0 else "strut" if force < 0 else "inactive"
        stroke = 1.5 + 7.5 * abs(force) / maximum
        lines.append(
            f'<line class="member {kind}" x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" style="stroke-width:{stroke:.2f}"/>'
        )
        if abs(force) > 1e-8:
            midpoint_x = 0.5 * (x1 + x2)
            midpoint_y = 0.5 * (y1 + y2)
            offset = -5.0 if member_id % 2 == 0 else 9.0
            force_labels.append(
                f'<text class="force-label" x="{midpoint_x:.2f}" '
                f'y="{midpoint_y + offset:.2f}">M{member_id} {force:+.1f}</text>'
            )
    for face in result.truss_model.external_faces:
        x1, y1 = point(face.start)
        x2, y2 = point(face.end)
        lines.append(f'<line class="face" x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>')
    active_node_ids = {int(node_id) for member in members for node_id in member}
    lines.extend(force_labels)
    for node_id, node in enumerate(nodes):
        if node_id not in active_node_ids:
            continue
        x, y = point(node)
        lines.append(f'<circle class="node" cx="{x:.2f}" cy="{y:.2f}" r="2.5"/>')
        lines.append(
            f'<text class="node-label" x="{x + 4:.2f}" y="{y - 4:.2f}">N{node_id}</text>'
        )
    return "".join(lines) + "</svg>"


def _table(records, columns, *, limit=24):
    if not records:
        return '<p class="muted">No records.</p>'
    head = "".join(f"<th>{escape(title)}</th>" for _, title in columns)
    shown = records if limit is None else records[:limit]
    body = "".join(
        "<tr>" + "".join(f"<td>{_fmt(row.get(key, ''))}</td>" for key, _ in columns) + "</tr>"
        for row in shown
    )
    note = (
        f'<p class="table-note">Showing {limit} of {len(records)} records.</p>'
        if limit is not None and len(records) > limit else ""
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{note}'


def _technical_appendix(records, combinations):
    """Return collapsible, complete calculation tables grouped by load case."""
    nodes = _table(
        records.get("nodes", []),
        [("node_id", "Node"), ("x", "x (in)"), ("y", "y (in)")], limit=None,
    )
    sections = [
        '<details class="technical"><summary>Node coordinate reference '
        f'({len(records.get("nodes", []))} nodes)</summary>{nodes}</details>'
    ]
    definitions = (
        ("Member forces", "common_member_forces", (
            ("member_id", "Member"), ("candidate_id", "Candidate"),
            ("node_i", "Node i"),
            ("node_j", "Node j"), ("force_type", "Type"),
            ("force", "Force (kip)"),
        )),
        ("Support reactions", "reactions", (
            ("node_id", "Node"), ("direction", "Direction"),
            ("reaction", "Reaction (kip)"),
        )),
        ("Strut checks", "strut_checks", (
            ("member_id", "Member"), ("force", "Force (kip)"),
            ("strut_width", "Width (in)"), ("capacity", "Capacity (kip)"),
            ("dc_ratio", "D/C"), ("status", "Status"),
        )),
        ("External nodal faces", "external_nodal_checks", (
            ("node_id", "Node"), ("group_label", "Zone"),
            ("face_type", "Face"), ("demand", "Demand (kip)"),
            ("face_width", "Width (in)"), ("capacity", "Capacity (kip)"),
            ("dc_ratio", "D/C"), ("status", "Status"),
        )),
        ("Interior nodal faces", "interior_nodal_checks", (
            ("node_id", "Node"), ("group_label", "Zone"),
            ("face_type", "Face"), ("demand", "Demand (kip)"),
            ("face_width", "Width (in)"), ("capacity", "Capacity (kip)"),
            ("dc_ratio", "D/C"), ("status", "Status"),
        )),
    )
    for combination in combinations:
        inner = []
        count = 0
        for title, key, columns in definitions:
            rows = [
                row for row in records.get(key, [])
                if row.get("combination") == combination
            ]
            count += len(rows)
            inner.append(
                f'<details class="technical-sub"><summary>{escape(title)} '
                f'({len(rows)})</summary>{_table(rows, columns, limit=None)}</details>'
            )
        sections.append(
            f'<details class="technical"><summary>{escape(combination)} - '
            f'complete technical data ({count} records)</summary>{"".join(inner)}</details>'
        )
    return "".join(sections)


def build_pier_cap_html_report(
    *, project, cap, materials, detailing, code_profile, common_analysis,
    tie_layouts, anchorage, cage_reviews, strut_checks,
    external_nodal_checks, interior_nodal_checks, calculation_records=None,
    crack_control=(), reinforcement_source="selected", metadata=None,
):
    """Build a portable, print-ready HTML calculation report."""
    records = calculation_records or {}
    metadata = metadata or {}
    checks = []
    for kind, mapping in (
        ("Strut", strut_checks), ("External node", external_nodal_checks),
        ("Interior node", interior_nodal_checks),
    ):
        for combination, items in mapping.items():
            for item in items:
                if kind == "Strut":
                    reference = f"Member M{getattr(item, 'member_id', '?')}"
                else:
                    reference = (
                        f"Node N{getattr(item, 'node_id', '?')} - "
                        f"{getattr(item, 'group_label', 'nodal zone')} - "
                        f"{getattr(item, 'face_type', 'face').replace('_', ' ')}"
                    )
                checks.append((
                    float(item.dc_ratio), kind, combination, reference, item.status,
                ))
    checks.sort(reverse=True)
    governing = checks[0][0] if checks else 0.0
    overall_ok = governing <= 1.0 and all(x.status == "OK" for x in cage_reviews) and all(x.status == "OK" for x in anchorage)
    status, css = ("PASS", "ok") if overall_ok else ("REVIEW", "warn")
    cards = (
        ("Overall", status, css), ("Governing D/C", f"{governing:.3f}", css),
        ("Retained members", str(len(common_analysis.members)), ""),
        ("Load combinations", str(len(common_analysis.case_results)), ""),
        ("Force reversals", str(len(common_analysis.force_reversals)), ""),
    )
    card_html = "".join(f'<div class="metric {c}"><span>{escape(a)}</span><strong>{escape(b)}</strong></div>' for a, b, c in cards)
    figures = "".join(
        f'<figure><figcaption>{escape(name)}</figcaption>{_force_flow_svg(common_analysis, name, cap)}<div class="legend"><span class="compression">Compression / strut</span><span class="tension">Tension / tie</span></div></figure>'
        for name in common_analysis.case_results
    )
    dc_html = "".join(
        f'<div class="dc-row"><span>{escape(kind)} · {escape(combo)} #{index}</span><div class="bar"><i style="width:{min(dc, 1) * 100:.1f}%"></i></div><strong>{dc:.3f}</strong><em class="{"ok" if item_status == "OK" else "warn"}">{escape(item_status)}</em></div>'
        for dc, kind, combo, index, item_status in checks[:12]
    )
    dc_html = "".join(
        f'<div class="dc-row"><span><b>{escape(kind)} - {escape(reference)}</b>'
        f'<small>{escape(combo)}</small></span><div class="bar"><i '
        f'style="width:{min(dc, 1) * 100:.1f}%"></i></div>'
        f'<strong>{dc:.3f}</strong><em class="'
        f'{"ok" if item_status == "OK" else "warn"}">{escape(item_status)}</em></div>'
        for dc, kind, combo, reference, item_status in checks[:12]
    )
    reinforcement = "".join(
        f'<div class="rebar-item"><strong>{escape(layer.title())}</strong><span>{layout.bar_count}-#{layout.bar_size} · A<sub>s</sub> = {layout.as_provided:.2f} in² · {layout.layers} layer(s)</span></div>'
        for layer, layout in tie_layouts.items()
    )
    reinforcement = "".join(
        f'<div class="rebar-item"><strong>{escape(layer.title())}</strong>'
        f'<span>A<sub>s,req</sub> = {layout.as_required:.2f} in² - '
        f'{escape(reinforcement_source)} {layout.bar_count}-#{layout.bar_size}, '
        f'A<sub>s</sub> = {layout.as_provided:.2f} in² - '
        f'{layout.layers} layer(s) - {layout.status}</span></div>'
        for layer, layout in tie_layouts.items()
    )
    crack_control_html = "".join(
        f'<div class="rebar-item"><strong>{item.direction.title()}</strong>'
        f'<span>A<sub>s,set</sub> = {item.steel_area_per_spacing:.2f} in² @ '
        f'{item.selected_spacing:.1f} in o.c. - '
        f'ρ = {item.provided_ratio:.4f} / {item.required_ratio:.4f} req. - '
        f'{item.status}</span></div>'
        for item in crack_control
    )
    anchor_rows = [{"layer": x.layer, "end": x.end, "available": float(x.available_length), "required": float(x.required_development_length), "type": x.anchorage_type, "status": x.status} for x in anchorage]
    quality, reversals = records.get("model_quality", []), records.get("force_reversals", [])
    title = escape(project.get("name", "Pier-Cap STM"))
    table_index = [{"table": key, "records": len(value)} for key, value in records.items()]
    technical_appendix = _technical_appendix(
        records, common_analysis.case_results.keys()
    )
    version_rows = [{
        "revision": metadata.get("project_revision", "not assigned"),
        "tool": metadata.get("tool_version", "n/a"),
        "notebook": metadata.get("notebook_template_version", "n/a"),
        "report": metadata.get("html_report_version", "n/a"),
        "input": metadata.get("input_fingerprint", "n/a"),
        "result": metadata.get("result_fingerprint", "n/a"),
        "commit": metadata.get("source_commit", "n/a"),
        "generated": metadata.get("generated_at_utc", "n/a"),
    }]
    version_html = "".join(
        f'<div><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>'
        for label, value in (
            ("Project revision", version_rows[0]["revision"]),
            ("Tool", version_rows[0]["tool"]),
            ("Notebook", version_rows[0]["notebook"]),
            ("Report", version_rows[0]["report"]),
            ("Input ID", version_rows[0]["input"]),
            ("Result ID", version_rows[0]["result"]),
            ("Source commit", version_rows[0]["commit"]),
            ("Generated UTC", version_rows[0]["generated"]),
        )
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — STM Calculation Report</title><style>
:root{{--ink:#17232d;--muted:#60717c;--line:#d9e0e3;--paper:#fff;--wash:#f3f6f7;--navy:#173f5f;--blue:#2878a6;--red:#bb4d42;--green:#26734d;--amber:#9a6415}}
*{{box-sizing:border-box}}body{{margin:0;background:#e8edef;color:var(--ink);font:14px/1.45 Arial,sans-serif}}main{{max-width:1080px;margin:28px auto;background:var(--paper);box-shadow:0 8px 30px #17232d18}}header{{padding:44px 52px 34px;border-top:10px solid var(--navy);background:linear-gradient(135deg,#fff 62%,#edf3f5)}}.eyebrow{{text-transform:uppercase;letter-spacing:.12em;color:var(--blue);font-weight:700;font-size:11px}}h1{{font:700 34px/1.12 Georgia,serif;margin:10px 0 8px}}.subtitle,.muted,.table-note{{color:var(--muted)}}.meta{{display:flex;gap:28px;margin-top:22px;color:var(--muted);flex-wrap:wrap}}.meta span{{display:inline-flex;gap:5px}}.meta b{{color:var(--ink)}}section{{padding:30px 52px;border-top:1px solid var(--line)}}h2{{font:700 23px Georgia,serif;margin:0 0 18px}}h3{{font-size:15px;margin:22px 0 10px}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}.metric{{border:1px solid var(--line);border-top:4px solid var(--navy);padding:13px}}.metric span{{display:block;color:var(--muted);font-size:11px;text-transform:uppercase}}.metric strong{{font-size:23px}}.metric.ok{{border-top-color:var(--green)}}.metric.warn{{border-top-color:var(--amber)}}.ok{{color:var(--green)}}.warn{{color:var(--amber)}}.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}.data-list{{margin:0;display:grid;grid-template-columns:1fr 1fr}}.data-list div{{padding:10px 0;border-bottom:1px solid var(--line)}}.data-list dt{{color:var(--muted);font-size:11px;text-transform:uppercase}}.data-list dd{{margin:2px 0 0;font-weight:700}}figure{{margin:0 0 24px;border:1px solid var(--line);background:#fbfcfc}}figcaption{{font-weight:700;padding:12px 16px;border-bottom:1px solid var(--line)}}svg{{display:block;width:100%;height:auto}}.cap{{fill:#f6f2eb;stroke:#99a6ad;stroke-width:1.5}}.member{{stroke-linecap:round;opacity:.9}}.strut{{stroke:var(--red)}}.tie{{stroke:var(--blue)}}.inactive{{stroke:#c7cdd0}}.node{{fill:#fff;stroke:#283c48;stroke-width:1}}.face{{stroke:#273d4a;stroke-width:7}}.legend{{display:flex;gap:22px;padding:8px 16px 12px;color:var(--muted);font-size:11px}}.legend span:before{{content:'';display:inline-block;width:18px;border-top:4px solid;margin-right:6px}}.legend .compression:before{{border-color:var(--red)}}.legend .tension:before{{border-color:var(--blue)}}.dc-row{{display:grid;grid-template-columns:190px 1fr 52px 45px;align-items:center;gap:10px;margin:9px 0;font-size:12px}}.bar{{height:10px;background:#e8edef;border:1px solid #c5d0d5;border-radius:5px;overflow:hidden}}.bar i{{display:block;height:100%;background:var(--blue)}}.dc-row em{{font-style:normal;font-weight:700}}.rebar-item{{padding:13px 0;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:15px}}.scope{{border-left:5px solid var(--navy);background:var(--wash);padding:16px 18px;break-inside:avoid}}.table-wrap{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{text-align:left;padding:8px;border-bottom:1px solid var(--line);white-space:nowrap}}th{{background:var(--wash)}}details{{margin-top:12px;border:1px solid var(--line);padding:12px}}summary{{cursor:pointer;font-weight:700}}footer{{padding:20px 52px;background:var(--navy);color:#dfe9ed;font-size:11px}}
.meta span+span:before{{content:'|';color:#aebbc2;margin-right:5px}}.version-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}}.version-grid div{{background:#fff;padding:10px}}.version-grid span{{display:block;color:var(--muted);font-size:10px;text-transform:uppercase}}.version-grid strong{{display:block;margin-top:3px;font-size:12px;overflow-wrap:anywhere}}.force-label,.node-label{{font:700 7px Arial,sans-serif;fill:#21333e;paint-order:stroke;stroke:#fff;stroke-width:2px;stroke-linejoin:round}}.force-label{{text-anchor:middle;font-size:8px}}.node-label{{fill:#536873}}.dc-row{{grid-template-columns:minmax(280px,2fr) 1fr 52px 45px}}.dc-row span b,.dc-row span small{{display:block}}.dc-row span small{{color:var(--muted);margin-top:2px}}details.technical{{border-left:4px solid var(--blue)}}details.technical-sub{{margin:10px 0 0;background:#fbfcfc}}.detail-controls{{display:flex;gap:8px;margin:14px 0}}.detail-controls button{{border:1px solid var(--navy);border-radius:3px;background:#fff;color:var(--navy);font-weight:700;padding:8px 13px;cursor:pointer}}.detail-controls button:hover{{background:var(--navy);color:#fff}}
@media(max-width:760px){{main{{margin:0}}header,section{{padding:26px 22px}}.metrics{{grid-template-columns:1fr 1fr}}.grid-2{{grid-template-columns:1fr}}.meta{{display:block}}.dc-row{{grid-template-columns:minmax(180px,2fr) 1fr 44px 36px}}}}@media print{{*{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}body{{background:#fff}}main{{margin:0;max-width:none;box-shadow:none}}header{{padding-top:28px}}.metrics{{grid-template-columns:repeat(5,1fr)}}.metric{{padding:9px}}.metric strong{{font-size:18px}}h2,h3,figcaption,summary{{break-after:avoid}}figure,.rebar-item{{break-inside:avoid}}.detail-controls{{display:none}}@page{{size:letter;margin:.45in}}}}</style></head><body><main>
<header><div class="eyebrow">Strut-and-tie model · calculation report</div><h1>{title}</h1><div class="subtitle">Two-dimensional pier-cap strength and detailing review</div><div class="meta"><span><b>Designer</b> {escape(project.get('designer','Not specified'))}</span><span><b>Date</b> {escape(project.get('date','Not specified'))}</span><span><b>Basis</b> {escape(code_profile['name'])}</span></div></header>
<section><h2>Document control</h2><div class="version-grid">{version_html}</div></section>
<section><h2>Design snapshot</h2><div class="metrics">{card_html}</div><p class="muted">Status combines strut, nodal-face, anchorage, and section-level cage checks. Engineering review remains required.</p></section>
<section><h2>Inputs and assumptions</h2><div class="grid-2"><dl class="data-list"><div><dt>Length</dt><dd>{cap['length']} in</dd></div><div><dt>Depth</dt><dd>{cap['depth']} in</dd></div><div><dt>Width</dt><dd>{cap['width']} in</dd></div><div><dt>Clear cover</dt><dd>{detailing['clear_cover']} in</dd></div><div><dt>Concrete f'c</dt><dd>{materials['fc_ksi']} ksi</dd></div><div><dt>Steel fy</dt><dd>{materials['fy_ksi']} ksi</dd></div></dl><div class="scope"><strong>Design basis</strong><p>{escape(code_profile['resistance_factor_status'])}</p><p>Maximum aggregate: {detailing['maximum_aggregate_size']} in. Inputs shown here are explicit and editable in the notebook.</p></div></div></section>
<section><h2>Force flow</h2><p class="muted">Line weight is proportional to member-force magnitude within each combination.</p>{figures}</section>
<section><h2>Reinforcement and anchorage</h2><div class="grid-2"><div><h3>Continuous tie reinforcement</h3>{reinforcement}<h3>Orthogonal crack-control grid</h3>{crack_control_html}</div><div><h3>Anchorage development</h3>{_table(anchor_rows,[('layer','Layer'),('end','End'),('available','Avail. (in)'),('required','Req. (in)'),('type','Detail'),('status','Status')])}</div></div></section>
<section><h2>Governing utilization</h2><p class="muted">Highest demand/capacity checks shown first. A value of 1.000 is full design resistance.</p>{dc_html}</section>
<section class="model-review"><h2>Model review</h2><div class="grid-2"><div><h3>Quality and equilibrium</h3>{_table(quality,[('combination','Combination'),('selected_member_count','Members'),('maximum_node_degree','Max degree'),('equilibrium_residual','Eq. residual')])}</div><div><h3>Force reversals</h3>{_table(reversals,[('candidate_id','Member'),('maximum_tension','Max tension'),('maximum_compression','Max compression')])}</div></div><details open><summary>Calculation table index</summary><p class="muted">Companion JSON/CSV exports contain the complete auditable records.</p>{_table(table_index,[('table','Table'),('records','Records')],limit=100)}</details></section>
<section id="technical-data"><h2>Technical calculation tables</h2><p class="muted">Expand a load case to review every member force, reaction, strut check, and nodal-face check. Node IDs correspond to the force-flow diagrams.</p><div class="detail-controls"><button type="button" onclick="setTechnicalDetails(true)">Expand all</button><button type="button" onclick="setTechnicalDetails(false)">Collapse all</button></div>{technical_appendix}</section>
<section><h2>Scope and limitations</h2><div class="scope">This is a two-dimensional STM analysis. Finite bearing and pile/shaft faces are represented by centroid resultants. Final three-dimensional bar positioning and clash review, reinforcing drawings, foundation design, project load development, and independent engineering approval remain outside this tool.</div></section><footer>Generated from the same normalized analysis results used by the pier-cap design notebook. Review values against project criteria before issue.</footer>
</main><script>function setTechnicalDetails(open){{document.querySelectorAll('#technical-data details').forEach(function(item){{item.open=open;}});}}</script></body></html>'''


def write_calculation_report(report, path):
    """Write a generated Markdown calculation summary."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(report), encoding="utf-8")
    return path


def write_html_report(report, path):
    """Write a generated portable HTML calculation report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(report), encoding="utf-8")
    return path
