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
    qpack_errors = [
        _query_pack_line(f)
        for f in findings
        if f.get("severity") == "error"
    ]
    qpack_warns = [
        _query_pack_line(f)
        for f in findings
        if f.get("severity") == "warn"
    ]

    def section(title: str, items: List[str]) -> str:
        if not items:
            return f"<h3>{_html_escape(title)}</h3><p>None</p>"
        return f"<h3>{_html_escape(title)}</h3><ul>" + "\n".join(items) + "</ul>"

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
  </style>
  </head>
<body>
  <h1>DD-Val Report</h1>
  <div class=\"summary\">
    <div><b>Generated:</b> {now}</div>
    <div><b>Rows:</b> {summary.get('rows', 0)} | <b>Cols:</b> {summary.get('cols', 0)} | <b>Dict fields:</b> {summary.get('dict_fields', 0)}</div>
  </div>
  {section('Must-fix (errors)', [_render_finding(f) for f in errors])}
  {section('Nice-to-fix (warnings)', [_render_finding(f) for f in warns])}
  {section('Info', [_render_finding(f) for f in infos])}
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
