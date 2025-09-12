from __future__ import annotations

"""dd-val CLI: validate dataset vs dictionary, write findings + HTML report."""

import argparse
import json
from pathlib import Path
import re
from typing import List

from .parse import load_dictionary, load_dataset_headers, iter_dataset_rows
from .checks import (
    Finding,
    build_summary,
    check_branching,
    check_checkbox_mismatch,
    check_columns,
    check_domains,
    check_matrix_consecutive,
    check_missingness_spike,
    check_rename_drift,
    check_types,
)
from .report import build_report_html


def _infer_prev_findings(cur_dir: Path) -> Path | None:
    """Infer previous findings.json path based on folder naming.

    Supported patterns:
    - flat:   name like "<base>_vN" -> previous "<base>_v(N-1)"
    - flat:   name like "<base>_perturbed_vN" -> previous "<base>_perturbed" (when N==2) or "<base>_perturbed_v(N-1)"
    - nested: name like "vN" under a project folder -> previous sibling "v(N-1)"
    Returns path to previous findings.json if it exists, else None.
    """
    name = cur_dir.name

    # Case: perturbed_vN special-casing v2 -> perturbed
    m = re.match(r"^(?P<base>.+_perturbed)_v(?P<ver>\d+)$", name)
    if m:
        base = m.group("base")
        ver = int(m.group("ver"))
        if ver == 2:
            cand = cur_dir.parent / base / "findings.json"
        else:
            cand = cur_dir.parent / f"{base}_v{ver-1}" / "findings.json"
        return cand if cand.exists() else None

    # Case: generic _vN suffix
    m = re.match(r"^(?P<base>.+)_v(?P<ver>\d+)$", name)
    if m:
        base = m.group("base")
        ver = int(m.group("ver"))
        if ver > 1:
            cand = cur_dir.parent / f"{base}_v{ver-1}" / "findings.json"
            return cand if cand.exists() else None

    # Case: nested vN folder
    m = re.match(r"^v(?P<ver>\d+)$", name)
    if m:
        ver = int(m.group("ver"))
        if ver > 1:
            cand = cur_dir.parent / f"v{ver-1}" / "findings.json"
            return cand if cand.exists() else None

    return None


def _infer_prev_from_pointer(cur_dir: Path) -> Path | None:
    """If a `.prev` file exists in `cur_dir`, interpret it as a pointer to
    the previous findings. Content may be a file path to findings.json or a
    directory path containing findings.json. Relative paths are resolved
    against `cur_dir`.
    """
    ptr = cur_dir / ".prev"
    if not ptr.exists():
        return None
    try:
        raw = ptr.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not raw:
        return None
    target = Path(raw)
    if not target.is_absolute():
        target = (cur_dir / target).resolve()
    # If a directory, assume findings.json inside
    if target.is_dir():
        target = target / "findings.json"
    return target if target.exists() else None


def _read_prev(prev_path: Path) -> dict | None:
    try:
        return json.loads(prev_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Validate REDCap dataset against dictionary and generate report + findings")
    ap.add_argument("--dict", dest="dict_path", required=True)
    ap.add_argument("--data", dest="data_path", required=True)
    ap.add_argument("--out", dest="findings_path", required=True, help="Output findings.json path")
    ap.add_argument("--html", dest="html_path", required=True, help="Output report.html path")
    ap.add_argument("--prev", dest="prev_findings", default=None, help="Previous findings.json for since-last-run diffs")
    ap.add_argument("--no-prev", action="store_true", help="Disable auto-detecting previous findings by folder naming (e.g., _vN)")
    args = ap.parse_args(argv)

    dict_path = Path(args.dict_path)
    data_path = Path(args.data_path)
    findings_path = Path(args.findings_path)
    html_path = Path(args.html_path)
    prev = Path(args.prev_findings) if args.prev_findings else None

    # If not explicitly provided, try .prev pointer then folder-naming inference
    if prev is None and not args.no_prev:
        cur_dir = findings_path.parent
        prev = _infer_prev_from_pointer(cur_dir) or _infer_prev_findings(cur_dir)

    dd = load_dictionary(dict_path)
    dataset_cols = load_dataset_headers(data_path)
    # Count rows cheaply
    n_rows = 0
    for _ in iter_dataset_rows(data_path):
        n_rows += 1

    # If previous findings are provided, pre-compute previous dataset columns
    prev_cols: set[str] = set()
    if prev and prev.exists():
        prev_obj = _read_prev(prev)
        if isinstance(prev_obj, dict):
            prev_sum = prev_obj.get("summary") or {}
            prev_cols = set(prev_sum.get("dataset_columns") or [])

    # Run checks
    findings: List[Finding] = []
    findings += check_columns(dd, dataset_cols)
    findings += check_rename_drift(dd, dataset_cols)
    findings += check_checkbox_mismatch(dd, dataset_cols)
    findings += check_types(dd, str(data_path), dataset_cols)
    findings += check_domains(dd, str(data_path), dataset_cols)
    from .checks import check_unit_anomaly
    findings += check_unit_anomaly(dd, str(data_path), dataset_cols)
    findings += check_missingness_spike(str(data_path), dataset_cols)
    findings += check_branching(dd, str(data_path), dataset_cols)
    findings += check_matrix_consecutive(dd)

    # Filter generic extras for new columns if this is a since-last-run scenario
    if prev_cols:
        new_cols = {c for c in dataset_cols if c not in prev_cols}
        findings = [
            f for f in findings
            if not (f.type == "extra_column_in_data" and f.variable in new_cols)
        ]

    # Convert to dicts
    findings_dicts = [f.as_dict() for f in findings]

    # Build summary (and embed current shapes to enable since-last-run in future)
    summary = build_summary(dd, dataset_cols, n_rows)

    # Since last run diffs (if prev provided and has summary)
    if prev and prev.exists():
        prev_obj = _read_prev(prev)
        if prev_obj and isinstance(prev_obj, dict):
            prev_sum = prev_obj.get("summary") or {}
            # new columns
            prev_cols2 = set(prev_sum.get("dataset_columns") or [])
            for col in dataset_cols:
                if col not in prev_cols2:
                    findings_dicts.append(
                        {
                            "type": "extra_column_since_last_run",
                            "variable": col,
                            "severity": "info",
                            "where": {"dataset_column": col},
                            "rows_affected": n_rows,
                        }
                    )
            # dictionary choices changes
            prev_choices = prev_sum.get("dict_choices") or {}
            cur_choices = summary.get("dict_choices") or {}
            for var, choices in cur_choices.items():
                prev_c = set(prev_choices.get(var) or [])
                cur_c = set(choices or [])
                added = sorted(list(cur_c - prev_c))
                if added:
                    findings_dicts.append(
                        {
                            "type": "domain_mismatch_since_last_run",
                            "variable": var,
                            "severity": "info",
                            "where": {"variable": var},
                            "observed_added": added,
                            "rows_affected": 0,
                        }
                    )

    # Write outputs
    result = {"summary": summary, "findings": findings_dicts}
    findings_path.parent.mkdir(parents=True, exist_ok=True)
    findings_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    html = build_report_html(summary, findings_dicts)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")

    # Also print a terse summary
    print(f"Findings: {len(findings_dicts)} | Rows={summary['rows']} Cols={summary['cols']} Dict={summary['dict_fields']}")


if __name__ == "__main__":
    main()
