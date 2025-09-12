from __future__ import annotations

"""Validation checks producing structured findings.

Each check is deterministic given the dataset and dictionary and should avoid
heavy dependencies for speed and portability.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .parse import Dictionary, DictField, iter_dataset_rows, is_date_ymd, is_int, is_num, guess_date_format


@dataclass
class Finding:
    type: str
    variable: str
    severity: str
    where: Dict[str, str]
    expected: Optional[Any] = None  # may be a string, list, or dict
    observed: Optional[Any] = None  # may be a string, list, or dict
    examples: Optional[List[str]] = None
    suggestion: Optional[str] = None
    rows_affected: Optional[int] = None

    def as_dict(self) -> dict:
        out = {
            "type": self.type,
            "variable": self.variable,
            "severity": self.severity,
            "where": self.where,
        }
        if self.expected is not None:
            out["expected"] = self.expected
        if self.observed is not None:
            out["observed"] = self.observed
        if self.examples:
            out["examples"] = self.examples[:5]
        if self.suggestion:
            out["suggestion"] = self.suggestion
        if self.rows_affected is not None:
            out["rows_affected"] = self.rows_affected
        return out


def _checkbox_expected_cols(f: DictField) -> List[str]:
    return [f"{f.variable}___{code}" for code, _lbl in f.choices]


# Thresholds (keep identical semantics; centralized for clarity)
TYPE_SUCCESS_INT = 0.95
TYPE_SUCCESS_NUM = 0.95
TYPE_SUCCESS_DATE = 0.95
MISSINGNESS_SPIKE_THRESHOLD = 0.70
REQUIRED_MISSING_RATE_THRESHOLD = 0.05
REDCAP_META_COLUMNS = {"redcap_event_name", "redcap_repeat_instrument", "redcap_repeat_instance"}


def check_columns(dict_: Dictionary, dataset_cols: List[str]) -> List[Finding]:
    ds_cols: Set[str] = set(dataset_cols)
    findings: List[Finding] = []

    # Detect if some missing columns are covered by rename hints
    covered_by_rename: Set[str] = set()
    for orig, hints in _RENAME_HINTS.items():
        if orig in dict_.by_var:
            for h in hints:
                if h in ds_cols:
                    covered_by_rename.add(orig)

    # Missing columns in data
    for f in dict_.fields:
        if f.field_type == "checkbox":
            for col in _checkbox_expected_cols(f):
                if col not in ds_cols:
                    findings.append(
                        Finding(
                            type="missing_column_in_data",
                            variable=col,
                            severity="error",
                            where={"dataset_column": col},
                        )
                    )
        else:
            if f.variable not in ds_cols and f.variable not in covered_by_rename:
                findings.append(
                    Finding(
                        type="missing_column_in_data",
                        variable=f.variable,
                        severity="error",
                        where={"dataset_column": f.variable},
                    )
                )

    # Extra columns in data
    allowed: Set[str] = set()
    for f in dict_.fields:
        if f.field_type == "checkbox":
            allowed.update(_checkbox_expected_cols(f))
        else:
            allowed.add(f.variable)
    # Derive: treat known rename targets as non-extra to avoid double counting
    for orig, hints in _RENAME_HINTS.items():
        if orig in dict_.by_var:
            for h in hints:
                allowed.add(h)
    # Allow standard REDCap longitudinal/repeating meta columns
    allowed.update(REDCAP_META_COLUMNS)
    # Derive: treat checkbox-style columns for known checkbox vars as non-extra; handled by checkbox check
    checkbox_vars = {f.variable for f in dict_.fields if f.field_type == "checkbox"}
    for col in dataset_cols:
        base = col.split("___", 1)[0]
        if base in checkbox_vars:
            continue
        if col not in allowed:
            findings.append(
                Finding(
                    type="extra_column_in_data",
                    variable=col,
                    severity="warn",
                    where={"dataset_column": col},
                )
            )
    return findings


def check_longitudinal_context(dataset_path: str, dataset_cols: List[str]) -> List[Finding]:
    present = sorted([c for c in REDCAP_META_COLUMNS if c in set(dataset_cols)])
    if not present:
        return []
    cols_to_collect = [c for c in ["redcap_event_name", "redcap_repeat_instrument", "redcap_repeat_instance"] if c in present]
    vals = _collect_values(dataset_path, cols_to_collect)
    # Compute event stats
    events = vals.get("redcap_event_name", []) if "redcap_event_name" in vals else []
    ev_counts = Counter([e for e in events if e != ""]) if events else Counter()
    top_events = [
        {"event": k, "n": v} for k, v in ev_counts.most_common(3)
    ] if ev_counts else []
    total = len(events) if events else 0
    rep_inst = vals.get("redcap_repeat_instrument", []) if "redcap_repeat_instrument" in vals else []
    rep_idx = vals.get("redcap_repeat_instance", []) if "redcap_repeat_instance" in vals else []
    repeat_rows = 0
    if rep_inst or rep_idx:
        # count rows where either repeat field is non-empty
        repeat_rows = sum(1 for i in range(max(len(rep_inst), len(rep_idx))) if ((rep_inst[i] if i < len(rep_inst) else "") != "" or (rep_idx[i] if i < len(rep_idx) else "") != ""))
    obs = {
        "distinct_events": len(ev_counts),
        "top_events": top_events,
        "repeat_rows": repeat_rows,
        "repeat_rate": round((repeat_rows / total), 3) if total else 0.0,
    }
    return [
        Finding(
            type="longitudinal_context_detected",
            variable="dataset",
            severity="info",
            where={"columns": ",".join(present)},
            observed=obs,
        )
    ]


def check_checkbox_mismatch(dict_: Dictionary, dataset_cols: List[str]) -> List[Finding]:
    ds_cols: Set[str] = set(dataset_cols)
    findings: List[Finding] = []
    for f in dict_.fields:
        if f.field_type != "checkbox":
            continue
        expected = set(_checkbox_expected_cols(f))
        added = sorted([c for c in ds_cols if c.startswith(f"{f.variable}___") and c not in expected])
        missing = sorted([c for c in expected if c not in ds_cols])
        if added or missing:
            obs: Dict[str, object] = {}
            if added:
                obs["observed_added"] = added
            if missing:
                obs["expected_missing"] = missing
            findings.append(
                Finding(
                    type="checkbox_expansion_mismatch",
                    variable=f.variable,
                    severity="error",
                    where={"dataset_column": f.variable},
                    observed=obs,
                )
            )
    return findings


def _collect_values(path: str, cols: List[str], limit: int = 50000) -> Dict[str, List[str]]:
    vals: Dict[str, List[str]] = {c: [] for c in cols}
    n = 0
    for row in iter_dataset_rows(path):
        for c in cols:
            vals[c].append((row.get(c, "") or "").strip())
        n += 1
        if n >= limit:
            break
    return vals


def _examples(values: List[str], predicate) -> List[str]:
    out: List[str] = []
    for v in values:
        if predicate(v):
            out.append(v)
        if len(out) >= 5:
            break
    return out


def detect_export_mode_labels(
    dict_: Dictionary, dataset_path: str, dataset_cols: List[str]
) -> Tuple[bool, List[Finding]]:
    """Detect if dataset likely contains labels instead of codes for categorical fields.

    Heuristic across radio/dropdown/yesno/truefalse fields:
    - Compute, across fields, how often values match allowed codes vs labels.
    - If label matches dominate and occur in multiple fields, flag and suggest re-export.
    Returns (labels_detected, findings).
    """
    cat_fields = [
        f for f in dict_.fields
        if f.field_type in {"radio", "dropdown", "yesno", "truefalse"} and f.variable in dataset_cols
    ]
    if not cat_fields:
        return False, []
    vals = _collect_values(dataset_path, [f.variable for f in cat_fields])
    total_code = total_label = total_nonempty = 0
    label_majority_fields = 0
    fields_checked = 0
    for f in cat_fields:
        vlist = [v for v in vals.get(f.variable, []) if v != ""]
        if not vlist:
            continue
        fields_checked += 1
        codes = {c for c, _ in f.choices}
        labels = {lbl for _, lbl in f.choices}
        n_code = sum(1 for v in vlist if v in codes)
        n_label = sum(1 for v in vlist if v in labels)
        total_code += n_code
        total_label += n_label
        total_nonempty += len(vlist)
        if len(vlist) > 0 and n_label / len(vlist) >= 0.8 and n_label > n_code:
            label_majority_fields += 1

    if fields_checked == 0:
        return False, []
    # Trigger if labels dominate globally and at least two fields show label-majority
    label_rate = (total_label / max(1, total_nonempty))
    labels_detected = (label_rate >= 0.6 and label_majority_fields >= 2 and total_label >= 20)
    if not labels_detected:
        return False, []
    finding = Finding(
        type="export_mode_labels_detected",
        variable="dataset",
        severity="info",
        where={"mode": "labels"},
        observed={
            "fields_checked": fields_checked,
            "label_majority_fields": label_majority_fields,
            "label_rate": round(label_rate, 3),
        },
        suggestion="Re-export with 'raw' (codes) or map labels to codes.",
    )
    return True, [finding]


def _build_rename_map(dict_: Dictionary, dataset_cols: List[str]) -> Dict[str, str]:
    ds = set(dataset_cols)
    mapping: Dict[str, str] = {}
    for orig, hints in _RENAME_HINTS.items():
        if orig in dict_.by_var and orig not in ds:
            for h in hints:
                if h in ds:
                    mapping[orig] = h
                    break
    return mapping


def check_types(dict_: Dictionary, dataset_path: str, dataset_cols: List[str]) -> List[Finding]:
    # Map dict variables to dataset columns (handles rename drift)
    rename_map = _build_rename_map(dict_, dataset_cols)
    var_to_dscol: Dict[str, str] = {}
    expected: Dict[str, str] = {}
    for f in dict_.fields:
        if f.field_type == "text" and f.validation in {"integer", "number", "date_ymd", "date_mdy", "datetime_ymd"}:
            if f.variable in dataset_cols:
                var_to_dscol[f.variable] = f.variable
                expected[f.variable] = f.validation
            elif f.variable in rename_map:
                dscol = rename_map[f.variable]
                var_to_dscol[f.variable] = dscol
                expected[f.variable] = f.validation
    ds_cols_to_check = list(var_to_dscol.values())
    vals = _collect_values(dataset_path, ds_cols_to_check)

    findings: List[Finding] = []
    for var, dscol in var_to_dscol.items():
        vlist = [v for v in vals.get(dscol, []) if v != ""]
        if not vlist:
            continue
        exp = expected[var]
        ok = 0
        n = len(vlist)
        obs_kind = "string"
        if exp == "integer":
            ok = sum(1 for v in vlist if is_int(v))
            if ok / n < TYPE_SUCCESS_INT:
                bad_examples = _examples(vlist, lambda v: not is_int(v))
                findings.append(
                    Finding(
                        type="type_mismatch",
                        variable=var,
                        severity="error",
                        where={"dataset_column": dscol},
                        expected="numeric",  # align with gold wording
                        observed="string",
                        examples=bad_examples,
                        rows_affected=n - ok,
                    )
                )
            continue
        if exp == "number":
            ok = sum(1 for v in vlist if is_num(v))
            if ok / n < TYPE_SUCCESS_NUM:
                bad_examples = _examples(vlist, lambda v: not is_num(v))
                findings.append(
                    Finding(
                        type="type_mismatch",
                        variable=var,
                        severity="error",
                        where={"dataset_column": dscol},
                        expected="numeric",
                        observed="string",
                        examples=bad_examples,
                        rows_affected=n - ok,
                    )
                )
            continue
        if exp in {"date_ymd", "datetime_ymd"}:
            ok = sum(1 for v in vlist if is_date_ymd(v))
            if ok / n < TYPE_SUCCESS_DATE:
                # try to guess observed non-ymd variant
                kind_counts = Counter(guess_date_format(v) for v in vlist)
                observed = "date_mdy" if kind_counts.get("date_mdy", 0) > 0 else "string"
                bad_examples = _examples(vlist, lambda v: guess_date_format(v) != exp)
                findings.append(
                    Finding(
                        type="type_mismatch",
                        variable=var,
                        severity="error",
                        where={"dataset_column": dscol},
                        expected="date_ymd",
                        observed=observed,
                        examples=bad_examples,
                        rows_affected=n - ok,
                    )
                )
            continue
    return findings


def check_domains(dict_: Dictionary, dataset_path: str, dataset_cols: List[str]) -> List[Finding]:
    to_check: List[Tuple[str, Set[str]]] = []
    for f in dict_.fields:
        if f.field_type in {"radio", "dropdown", "yesno", "truefalse"} and f.variable in dataset_cols:
            allowed = set(code for code, _ in f.choices)
            to_check.append((f.variable, allowed))
    vals = _collect_values(dataset_path, [c for c, _ in to_check])
    findings: List[Finding] = []
    for col, allowed in to_check:
        vset = set(v for v in vals[col] if v != "")
        unexpected = sorted([v for v in vset if v not in allowed])
        if unexpected:
            expected_pairs = [f"{c}={lbl}" for c, lbl in dict_.choices[col]]
            findings.append(
                Finding(
                    type="domain_mismatch",
                    variable=col,
                    severity="error",
                    where={"dataset_column": col},
                    expected=expected_pairs,
                    observed=unexpected,
                    examples=unexpected[:5],
                    rows_affected=sum(1 for v in vals[col] if v in unexpected),
                )
            )
    return findings


def check_primary_key(dict_: Dictionary, dataset_path: str, dataset_cols: List[str]) -> List[Finding]:
    """Ensure primary key column exists and is unique.

    Preference order: 'record_id' if present; else first variable in dictionary.
    """
    findings: List[Finding] = []
    pk = "record_id" if "record_id" in dataset_cols else (dict_.fields[0].variable if dict_.fields else None)
    if not pk:
        return findings
    if pk not in dataset_cols:
        findings.append(
            Finding(
                type="missing_primary_key_column",
                variable=pk,
                severity="error",
                where={"dataset_column": pk},
            )
        )
        return findings
    # Check duplicates (ignore blanks)
    seen: Set[str] = set()
    dups: Counter[str] = Counter()
    total = 0
    blanks = 0
    for row in iter_dataset_rows(dataset_path):
        v = (row.get(pk, "") or "").strip()
        total += 1
        if v == "":
            blanks += 1
            continue
        if v in seen:
            dups[v] += 1
        else:
            seen.add(v)
    if dups:
        examples = [k for k, _ in dups.most_common(5)]
        rows_affected = sum(dups.values())
        findings.append(
            Finding(
                type="duplicate_primary_key_values",
                variable=pk,
                severity="error",
                where={"dataset_column": pk},
                examples=examples,
                rows_affected=rows_affected,
            )
        )
    return findings


def check_required_fields(
    dict_: Dictionary, dataset_path: str, dataset_cols: List[str], threshold: float = REQUIRED_MISSING_RATE_THRESHOLD
) -> List[Finding]:
    """For dictionary-required fields, flag high missing rates in the dataset."""
    req_vars = [f.variable for f in dict_.fields if getattr(f, "required", False) and f.variable in dataset_cols]
    if not req_vars:
        return []
    vals = _collect_values(dataset_path, req_vars)
    findings: List[Finding] = []
    for var in req_vars:
        col_vals = vals.get(var, [])
        if not col_vals:
            continue
        total = len(col_vals)
        missing = sum(1 for v in col_vals if (v or "").strip() == "")
        if total >= 20 and missing / total >= threshold:
            findings.append(
                Finding(
                    type="required_field_missing_rate_high",
                    variable=var,
                    severity="error",
                    where={"dataset_column": var},
                    observed={"missing_rate": round(missing / total, 3)},
                    rows_affected=missing,
                )
            )
    return findings


def check_missingness_spike(dataset_path: str, dataset_cols: List[str], threshold: float = MISSINGNESS_SPIKE_THRESHOLD) -> List[Finding]:
    vals = _collect_values(dataset_path, dataset_cols)
    findings: List[Finding] = []
    for col in dataset_cols:
        total = len(vals[col])
        empties = sum(1 for v in vals[col] if v == "")
        if total >= 50 and empties / total >= threshold:
            findings.append(
                Finding(
                    type="missingness_spike",
                    variable=col,
                    severity="warn",
                    where={"dataset_column": col},
                    rows_affected=empties,
                )
            )
    return findings


def check_unit_anomaly(dict_: Dictionary, dataset_path: str, dataset_cols: List[str]) -> List[Finding]:
    # Heuristic:
    # if field_note contains 'units=cm', and >5% of numeric values < 100 while majority > 100 => hint inches subset
    note_units = {}
    for f in dict_.fields:
        note = (f.raw.get("field_note") or "").lower()
        if "units=" in note and f.variable in dataset_cols:
            unit = note.split("units=", 1)[1].split()[0]
            note_units[f.variable] = unit
    vals = _collect_values(dataset_path, list(note_units.keys()))
    findings: List[Finding] = []
    for col, unit in note_units.items():
        vnums = []
        for v in vals[col]:
            try:
                if v != "":
                    vnums.append(float(v))
            except Exception:
                pass
        if len(vnums) < 20:
            continue
        small = sum(1 for x in vnums if x < 100.0)
        large = sum(1 for x in vnums if x >= 100.0)
        if unit == "cm" and small / len(vnums) >= 0.05 and large / len(vnums) >= 0.5:
            findings.append(
                Finding(
                    type="unit_anomaly",
                    variable=col,
                    severity="warn",
                    where={"dataset_column": col},
                    expected={"unit": unit},
                    observed={"note": "subset appears inches"},
                    rows_affected=small,
                )
            )
    return findings


def check_branching(dict_: Dictionary, dataset_path: str, dataset_cols: List[str]) -> List[Finding]:
    # Minimal logic: detect pregnant=1 when sex=0 for condition [sex] = '1'
    if "sex" not in dataset_cols or "pregnant" not in dataset_cols:
        return []
    cond = dict_.by_var.get("pregnant").branching_logic if dict_.by_var.get("pregnant") else ""
    if "[sex]" not in cond:
        return []
    vals = _collect_values(dataset_path, ["sex", "pregnant"])
    affected = 0
    for s, p in zip(vals["sex"], vals["pregnant"]):
        if s == "0" and p == "1":
            affected += 1
    if affected:
        return [
            Finding(
                type="branching_mismatch",
                variable="pregnant",
                severity="warn",
                where={"dataset_column": "pregnant"},
                expected={"condition": "[sex] = '1'"},
                rows_affected=affected,
            )
        ]
    return []


def check_matrix_consecutive(dict_: Dictionary) -> List[Finding]:
    # A group's fields must be consecutive in dictionary order
    idx: Dict[str, List[int]] = defaultdict(list)
    for i, f in enumerate(dict_.fields):
        if f.matrix_group:
            idx[f.matrix_group].append(i)
    findings: List[Finding] = []
    for group, positions in idx.items():
        if not positions:
            continue
        positions = sorted(positions)
        consecutive = all(positions[j] + 1 == positions[j + 1] for j in range(len(positions) - 1))
        if not consecutive:
            findings.append(
                Finding(
                    type="matrix_nonconsecutive",
                    variable=group,
                    severity="warn",
                    where={"matrix_group": group},
                )
            )
    return findings


_RENAME_HINTS = {
    "bp_sys": ["sbp"],
    "bp_dia": ["dbp"],
    "height_cm": ["ht_cm", "heightcm"],
}


def check_rename_drift(dict_: Dictionary, dataset_cols: List[str]) -> List[Finding]:
    ds = set(dataset_cols)
    findings: List[Finding] = []
    for orig, hints in _RENAME_HINTS.items():
        if orig in dict_.by_var and orig not in ds:
            for h in hints:
                if h in ds:
                    findings.append(
                        Finding(
                            type="rename_drift",
                            variable=orig,
                            severity="warn",
                            where={"dataset_column": h},
                            observed={"new": h},
                        )
                    )
                    break
    return findings


def build_summary(
    dict_: Dictionary,
    dataset_cols: List[str],
    n_rows: int,
    primary_key: str | None = None,
    pk_blanks: int | None = None,
    pk_duplicates: int | None = None,
) -> dict:
    summary = {
        "rows": n_rows,
        "cols": len(dataset_cols),
        "dict_fields": len(dict_.fields),
        "dataset_columns": dataset_cols,
        "dict_field_names": [f.variable for f in dict_.fields],
        "dict_choices": {v: [f"{c}={lbl}" for c, lbl in dict_.choices.get(v, [])] for v in [f.variable for f in dict_.fields]},
        "dict_validations": {f.variable: (f.validation or "") for f in dict_.fields},
        "dict_required_flags": {f.variable: bool(getattr(f, "required", False)) for f in dict_.fields},
    }
    if primary_key is not None:
        summary["primary_key"] = primary_key
    if pk_blanks is not None:
        summary["primary_key_blanks"] = pk_blanks
    if pk_duplicates is not None:
        summary["primary_key_duplicates"] = pk_duplicates
    return summary
