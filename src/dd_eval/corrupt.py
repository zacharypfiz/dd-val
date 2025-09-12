from __future__ import annotations

"""Deterministic corruption recipes to generate perturbed datasets.

NOTE: Some branches currently use `random.random()` instead of the provided RNG,
which introduces minor non-determinism across runs. We keep the behavior for
backward compatibility. Consider switching to the provided `rng` everywhere
in a future revision when you are ready to reseed the corpus.
"""

import copy
import random
from typing import Dict, List, Tuple

from .synth import dataset_headers


Issue = Dict[str, object]


def _log(gold: List[Issue], type_: str, variable: str, **kwargs) -> None:
    rec: Issue = {"type": type_, "variable": variable}
    rec.update(kwargs)
    gold.append(rec)


def _dict_by_var(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {r["variable_name"]: r for r in rows}


def _choice_pairs(r: Dict[str, str]) -> List[Tuple[str, str]]:
    raw = r.get("choices_calculations_or_slider_labels", "").strip()
    pairs: List[Tuple[str, str]] = []
    for part in raw.split("|") if raw else []:
        part = part.strip()
        if not part:
            continue
        if "," in part:
            v, lbl = part.split(",", 1)
            pairs.append((v.strip(), lbl.strip()))
    return pairs


def apply_corruptions(
    dict_rows: List[Dict[str, str]],
    data_rows: List[Dict[str, str]],
    seed: int,
    enable: Dict[str, bool] | None = None,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Issue]]:
    """Returns (dict_rows', data_rows', gold)"""
    rng = random.Random(seed)
    enable = enable or {}
    enable_default = True

    d_rows = copy.deepcopy(dict_rows)
    x_rows = copy.deepcopy(data_rows)
    gold: List[Issue] = []

    by_var = _dict_by_var(d_rows)
    data_cols = list(x_rows[0].keys()) if x_rows else []

    # 1) Missing/extra columns
    if enable.get("missing_extra_columns", enable_default) and data_cols:
        candidates = [v for v in by_var.keys() if v not in {"record_id"} and v in data_cols]
        if candidates:
            drop_v = rng.choice(candidates)
            for row in x_rows:
                if drop_v in row:
                    row.pop(drop_v)
            _log(gold, "missing_column_in_data", drop_v, rows_affected=len(x_rows))
        # Add extra data-only column
        extra_name = "extra_col"
        if extra_name not in data_cols:
            for row in x_rows:
                row[extra_name] = str(rng.randrange(0, 9999))
            _log(gold, "extra_column_in_data", extra_name, rows_affected=len(x_rows))

    # 2) Type drift (integers to strings; date format changes)
    if enable.get("type_drift", enable_default):
        # Numeric fields
        numeric_vars = [
            v
            for v, r in by_var.items()
            if r.get("text_validation_type_or_show_slider_number") in {"integer", "number"}
            and v in x_rows[0]
        ]
        for v in numeric_vars:
            n_aff = 0
            for row in x_rows:
                if rng.random() < 0.15 and row.get(v, "") != "":
                    row[v] = row[v] + "x"  # make non-coercible
                    n_aff += 1
            if n_aff:
                _log(gold, "type_mismatch", v, expected="numeric", observed="string", rows_affected=n_aff)
        # Date fields
        date_vars = [
            v
            for v, r in by_var.items()
            if r.get("text_validation_type_or_show_slider_number") in {"date_ymd"}
            and v in x_rows[0]
        ]
        for v in date_vars:
            n_aff = 0
            for row in x_rows:
                val = row.get(v, "")
                if val and rng.random() < 0.2:
                    # y-m-d -> m/d/Y
                    y, m, d = val.split("-")
                    row[v] = f"{m}/{d}/{y}"
                    n_aff += 1
            if n_aff:
                _log(gold, "type_mismatch", v, expected="date_ymd", observed="date_mdy", rows_affected=n_aff)

    # 3) Domain drift for categoricals (skip if label-export mode is enabled to avoid conflict)
    if enable.get("domain_drift", enable_default) and not enable.get("label_export", enable_default):
        cat_vars = [v for v, r in by_var.items() if r.get("field_type") in {"radio", "dropdown"} and v in x_rows[0]]
        if cat_vars:
            v = rng.choice(cat_vars)
            seen = set([row.get(v, "") for row in x_rows if row.get(v, "") != ""])
            # Inject unseen level
            injected = "9"
            affected = 0
            for row in x_rows:
                if rng.random() < 0.1:
                    row[v] = injected
                    affected += 1
            expected = [f"{code}={lbl}" for code, lbl in _choice_pairs(by_var[v])]
            observed = sorted(list({*seen, injected}))
            if affected:
                _log(
                    gold,
                    "domain_mismatch",
                    v,
                    expected=expected,
                    observed=observed,
                    rows_affected=affected,
                )

    # 4) Unit anomalies (height cm -> inches subset)
    if enable.get("unit_anomalies", enable_default) and "height_cm" in x_rows[0]:
        affected = 0
        for row in x_rows:
            val = row.get("height_cm", "")
            if val and "x" not in val and random.random() < 0.12:
                try:
                    cm = float(val)
                    inches = cm * 0.393701
                    row["height_cm"] = f"{inches:.1f}"
                    affected += 1
                except ValueError:
                    pass
        if affected:
            _log(gold, "unit_anomaly", "height_cm", expected_unit="cm", note="subset appears inches", rows_affected=affected)

    # 5) Missingness spikes (visit 2 fields)
    if enable.get("missingness_spikes", enable_default) and "visit_date_v2" in x_rows[0]:
        affected = 0
        for row in x_rows:
            if random.random() < 0.8:
                if row.get("visit_date_v2"):
                    row["visit_date_v2"] = ""
                    affected += 1
        if affected:
            _log(gold, "missingness_spike", "visit_date_v2", rows_affected=affected)

    # 6) Rename drift (bp_sys -> sbp or height_cm -> ht_cm)
    if enable.get("rename_drift", enable_default):
        target = None
        if "bp_sys" in x_rows[0]:
            target = ("bp_sys", "sbp")
        elif "height_cm" in x_rows[0]:
            target = ("height_cm", "ht_cm")
        if target:
            old, new = target
            for row in x_rows:
                if old in row:
                    row[new] = row.pop(old)
            _log(gold, "rename_drift", old, observed=new, rows_affected=len(x_rows))

    # 7) Checkbox expansion mismatch (add extra code column or drop one)
    if enable.get("checkbox_expansion", enable_default):
        # Use symptoms if present
        codes = None
        if "symptoms" in by_var:
            codes = [code for code, _ in _choice_pairs(by_var["symptoms"])]
        if codes:
            # Add a bogus column symptoms___999
            bogus = "symptoms___999"
            for row in x_rows:
                row[bogus] = "1" if random.random() < 0.05 else "0"
            _log(gold, "checkbox_expansion_mismatch", "symptoms", observed_added=[bogus], rows_affected=len(x_rows))

    # 8) Branching mismatch (pregnant with sex=Male)
    if enable.get("branching_mismatch", enable_default) and "sex" in x_rows[0] and "pregnant" in x_rows[0]:
        affected = 0
        for row in x_rows:
            if row.get("sex") == "0" and random.random() < 0.2:
                row["pregnant"] = "1"
                affected += 1
        if affected:
            _log(gold, "branching_mismatch", "pregnant", condition="[sex] = '1'", rows_affected=affected)

    # 9) Matrix break (non-consecutive rows in dictionary)
    if enable.get("matrix_break", enable_default):
        # Move one ADL row to the end
        idxs = [i for i, r in enumerate(d_rows) if r.get("matrix_group_name") == "adls"]
        if len(idxs) >= 2:
            i = random.choice(idxs)
            d_rows.append(d_rows.pop(i))
            _log(gold, "matrix_nonconsecutive", "adls", rows_affected=0)

    # 10) Primary key integrity issues
    if enable.get("primary_key", enable_default):
        # Prefer record_id if present
        pk = "record_id" if "record_id" in (x_rows[0] if x_rows else {}) else None
        if pk:
            mode = rng.choice(["duplicates", "missing_column"]) if len(x_rows) > 0 else "duplicates"
            if mode == "missing_column":
                for row in x_rows:
                    if pk in row:
                        row.pop(pk)
                _log(gold, "missing_primary_key_column", pk, rows_affected=len(x_rows))
            else:
                # Create duplicates by copying some earlier IDs into later rows
                ids = [row.get(pk, "") for row in x_rows]
                n_aff = 0
                for i in range(len(x_rows)):
                    if ids[i] and rng.random() < 0.1:
                        j = rng.randrange(0, max(1, i))
                        if ids[j]:
                            x_rows[i][pk] = ids[j]
                            n_aff += 1
                if n_aff:
                    _log(gold, "duplicate_primary_key_values", pk, rows_affected=n_aff)

    # 11) Required field missing rate (high)
    if enable.get("required_missing", enable_default):
        # Pick from known required fields in our synth dict (e.g., 'age' or 'sex')
        candidates = [v for v, r in by_var.items() if r.get("required_field", "").lower() == "y" and v in (x_rows[0] if x_rows else {})]
        if candidates:
            v = rng.choice(candidates)
            affected = 0
            for row in x_rows:
                if rng.random() < 0.3:  # 30% missing
                    row[v] = ""
                    affected += 1
            if affected:
                _log(gold, "required_field_missing_rate_high", v, rows_affected=affected)

    # 12) Label vs raw export (convert categorical codes to labels)
    if enable.get("label_export", enable_default):
        # Build mapping var: {code->label}
        cat_vars = [v for v, r in by_var.items() if r.get("field_type") in {"radio", "dropdown", "yesno", "truefalse"} and v in (x_rows[0] if x_rows else {})]
        if cat_vars:
            maps = {}
            for v in cat_vars:
                pairs = _choice_pairs(by_var[v])
                if not pairs and by_var[v].get("field_type") in {"yesno", "truefalse"}:
                    pairs = [("0", "No"), ("1", "Yes")] if by_var[v]["field_type"] == "yesno" else [("0", "False"), ("1", "True")]
                maps[v] = {c: lbl for c, lbl in pairs}
            # Convert values where mapping exists
            converted = 0
            for row in x_rows:
                for v in cat_vars:
                    val = row.get(v, "")
                    if val in maps.get(v, {}):
                        row[v] = maps[v][val]
                        converted += 1
            if converted:
                _log(gold, "export_mode_labels_detected", "dataset", rows_affected=len(x_rows))

    # 13) Longitudinal/repeating context columns
    if enable.get("longitudinal_context", enable_default):
        present = False
        for row in x_rows:
            row["redcap_event_name"] = row.get("redcap_event_name") or rng.choice(["baseline_arm_1", "followup_arm_1"])
            # Optional repeat fields, sparsely populated
            if rng.random() < 0.2:
                row["redcap_repeat_instrument"] = "followup"
                row["redcap_repeat_instance"] = str(rng.randrange(1, 4))
            present = True
        if present:
            _log(gold, "longitudinal_context_detected", "dataset", rows_affected=len(x_rows))

    return d_rows, x_rows, gold


def apply_since_last_run(
    dict_rows: List[Dict[str, str]], data_rows: List[Dict[str, str]], seed: int
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Issue]]:
    rng = random.Random(seed + 1)
    d2 = copy.deepcopy(dict_rows)
    x2 = copy.deepcopy(data_rows)
    gold: List[Issue] = []

    by_var = _dict_by_var(d2)

    # Add a new category to satisfaction
    if "satisfaction" in by_var:
        r = by_var["satisfaction"]
        raw = r.get("choices_calculations_or_slider_labels", "")
        if "5," not in raw:
            r["choices_calculations_or_slider_labels"] = (raw + " | 5,Outstanding").strip(" | ")
            _log(gold, "domain_mismatch_since_last_run", "satisfaction", observed_added=["5=Outstanding"], rows_affected=0)

    # Add a new column in data
    new_col = "new_since_last_run"
    for row in x2:
        row[new_col] = str(rng.randrange(0, 100))
    _log(gold, "extra_column_since_last_run", new_col, rows_affected=len(x2))

    return d2, x2, gold
