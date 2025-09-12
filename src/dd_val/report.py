from __future__ import annotations

"""Minimal HTML report renderer for findings.

Outputs a single-page report with sections and a compact Query Pack.
"""

from datetime import datetime
from typing import Dict, List


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _li(text: str) -> str:
    return f"<li>{_html_escape(text)}</li>"


def _render_finding(f: dict) -> str:
    variable = f.get("variable", "")
    ftype = f.get("type", "")
    sev = f.get("severity", "info").upper()
    where = f.get("where", {})
    examples = f.get("examples", []) or []
    rows_affected = f.get("rows_affected")
    extra = []
    if rows_affected is not None:
        extra.append(f"rows_affected={rows_affected}")
    # Show observed_added for since-last-run domain changes
    if isinstance(f.get("observed_added"), list) and f["observed_added"]:
        extra.append("added=" + ", ".join(str(x) for x in f["observed_added"][:5]))
    # Highlight primary column/location when present
    if isinstance(where, dict):
        if where.get("dataset_column"):
            extra.append(f"column={where['dataset_column']}")
        elif where.get("variable") and where["variable"] != variable:
            extra.append(f"where={where['variable']}")
    # Tailored extras for specific info types
    if ftype == "export_mode_labels_detected":
        ob = f.get("observed", {}) or {}
        if isinstance(ob, dict):
            if "label_rate" in ob:
                extra.append(f"label_rate={ob['label_rate']}")
            if "fields_checked" in ob and "label_majority_fields" in ob:
                extra.append(f"fields_checked={ob['fields_checked']} label_fields={ob['label_majority_fields']}")
            if "suppressed_domain_findings" in ob:
                extra.append(f"suppressed_domain_findings={ob['suppressed_domain_findings']}")
    if ftype == "longitudinal_context_detected":
        where_cols = f.get("where", {}).get("columns")
        if where_cols:
            extra.append(f"present={where_cols}")
        ob = f.get("observed", {}) or {}
        if isinstance(ob, dict):
            if "distinct_events" in ob and ob.get("distinct_events"):
                extra.append(f"distinct_events={ob['distinct_events']}")
            if ob.get("top_events"):
                # Render top 2
                tops = ob["top_events"][:2]
                tops_str = ", ".join(f"{t['event']}={t['n']}" for t in tops if 'event' in t and 'n' in t)
                if tops_str:
                    extra.append(f"top_events={tops_str}")
            if "repeat_rate" in ob:
                extra.append(f"repeat_rate={ob['repeat_rate']}")
    if examples:
        extra.append(f"examples: {', '.join(examples[:5])}")
    extra_str = f" — {'; '.join(extra)}" if extra else ""
    return f"<li><code>{_html_escape(variable)}</code> — <b>{_html_escape(ftype)}</b> [{_html_escape(sev)}]{_html_escape(extra_str)}</li>"


def _query_pack_line(f: dict) -> str:
    t = f.get("type")
    v = f.get("variable")
    ex = f.get("examples", []) or []
    if t == "missing_column_in_data":
        return f"{v}: Defined in dictionary but missing from dataset. Should this be added to the next export or removed from the dictionary?"
    if t == "extra_column_in_data":
        return f"{v}: Present in dataset but not in dictionary. Should we add it to the dictionary or exclude it from analysis?"
    if t == "domain_mismatch":
        exp = f.get("expected")
        return f"{v}: Observed values {ex[:5]} not in allowed codes {exp}. Map these or revise Column F choices?"
    if t == "type_mismatch":
        exp = f.get("expected")
        return f"{v}: Validated as {exp} but some values do not parse (e.g., {ex[:3]}). Should validation change or data be recoded?"
    if t == "unit_anomaly":
        return f"{v}: Numeric values suggest alternate unit for a subset. Confirm units or recode."
    if t == "checkbox_expansion_mismatch":
        return f"{v}: Checkbox columns do not match choices. Align dataset columns with Column F codes."
    if t == "rename_drift":
        newv = (f.get("observed", {}) or {}).get("new")
        if newv:
            return f"{v}: Appears renamed in dataset to '{newv}'. Align names or update dictionary."
        return f"{v}: Appears renamed in dataset. Align names or update dictionary."
    if t == "missing_primary_key_column":
        return f"{v}: Primary key column missing. Add this column to the export."
    if t == "duplicate_primary_key_values":
        return f"{v}: Duplicate primary key values exist (e.g., {ex[:3]}). Deduplicate or fix export."
    if t == "required_field_missing_rate_high":
        return f"{v}: Required field has high missing rate. Review branching or enforce entry."
    if t == "export_mode_labels_detected":
        return f"{v}: Dataset appears label-exported. Re-export in raw (codes) or map labels."
    if t == "matrix_nonconsecutive":
        return f"{v}: Matrix fields are not consecutive in dictionary. Reorder so they appear together."
    if t == "branching_mismatch":
        return f"{v}: Values appear outside branching logic. Confirm logic or data."
    return f"{v}: {t} — please review."


def build_report_html(summary: dict, findings: List[dict]) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    errors = [f for f in findings if f.get("severity") == "error"]
    warns = [f for f in findings if f.get("severity") == "warn"]
    infos = [f for f in findings if f.get("severity") == "info"]
    has_label_export = any(f.get("type") == "export_mode_labels_detected" for f in findings)
    # Sort Query Pack items by variable then type (groups by variable)
    err_sorted = sorted([f for f in findings if f.get("severity") == "error"], key=lambda x: (x.get("variable",""), x.get("type","")))
    warn_sorted = sorted([f for f in findings if f.get("severity") == "warn"], key=lambda x: (x.get("variable",""), x.get("type","")))
    qpack_errors = [_query_pack_line(f) for f in err_sorted]
    qpack_warns = [_query_pack_line(f) for f in warn_sorted]

    def section(title: str, items: List[str]) -> str:
        if not items:
            return f"<h3>{_html_escape(title)}</h3><p>None</p>"
        return f"<h3>{_html_escape(title)}</h3><ul>" + "\n".join(items) + "</ul>"

    # Primary key summary line
    pk = summary.get('primary_key')
    pk_line = ''
    if pk:
        dupe = int(summary.get('primary_key_duplicates') or 0)
        blank = int(summary.get('primary_key_blanks') or 0)
        extra = []
        if dupe:
            extra.append(f"duplicates={dupe}")
        if blank:
            extra.append(f"blanks={blank}")
        extra_s = f" ({'; '.join(extra)})" if extra else ''
        pk_line = f"<div><b>Primary key:</b> {pk}{extra_s}</div>"

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>DD-Val Report</title>
  <style>
    body {{ font-family: -apple-system, system-ui, sans-serif; margin: 24px; }}
    h1,h2,h3 {{ margin: 12px 0; }}
    code {{ background: #f2f2f2; padding: 1px 4px; border-radius: 3px; }}
    .summary {{ background: #fafafa; border: 1px solid #eee; padding: 12px; }}
    .notes {{ color: #555; font-size: 0.95em; margin-top: 12px; }}
  </style>
  </head>
<body>
  <h1>DD-Val Report</h1>
  <div class=\"summary\">
    <div><b>Generated:</b> {now}</div>
    <div><b>Rows:</b> {summary.get('rows', 0)} | <b>Cols:</b> {summary.get('cols', 0)} | <b>Dict fields:</b> {summary.get('dict_fields', 0)}</div>
    {pk_line}
  </div>
  {section('Must-fix (errors)', [_render_finding(f) for f in errors])}
  {section('Nice-to-fix (warnings)', [_render_finding(f) for f in warns])}
  {section('Info', [_render_finding(f) for f in infos])}
  {('<div class=\'notes\'><b>Note:</b> Domain mismatches were suppressed because the dataset appears label-exported.</div>' if has_label_export else '')}
  <h3>Query Pack</h3>
  <h4>Errors ({len(qpack_errors)})</h4>
  <ul>
    {''.join(_li(x) for x in qpack_errors) if qpack_errors else '<li>None</li>'}
  </ul>
  <h4>Warnings ({len(qpack_warns)})</h4>
  <ul>
    {''.join(_li(x) for x in qpack_warns) if qpack_warns else '<li>None</li>'}
  </ul>
</body>
</html>
"""
    return html
