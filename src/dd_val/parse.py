from __future__ import annotations

"""Parsing helpers for REDCap dictionary and CSV dataset.

This module purposefully avoids heavy dependencies; CSV is streamed with the
standard library. Normalization mirrors the REDCap A–R headers.
"""

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class DictField:
    variable: str
    form_name: str
    field_type: str
    field_label: str
    choices: List[Tuple[str, str]]
    validation: str
    vmin: Optional[str]
    vmax: Optional[str]
    identifier: bool
    required: bool
    branching_logic: str
    matrix_group: str
    raw: Dict[str, str]


@dataclass
class Dictionary:
    fields: List[DictField]
    by_var: Dict[str, DictField]
    choices: Dict[str, List[Tuple[str, str]]]
    matrix_groups: Dict[str, List[str]]


def _parse_choices(field_type: str, raw: str) -> List[Tuple[str, str]]:
    raw = (raw or "").strip()
    if field_type == "yesno":
        return [("0", "No"), ("1", "Yes")]
    if field_type == "truefalse":
        return [("0", "False"), ("1", "True")]
    if field_type not in {"radio", "dropdown", "checkbox"}:
        return []
    out: List[Tuple[str, str]] = []
    if not raw:
        return out
    for part in raw.split("|"):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            code, label = part.split(",", 1)
            out.append((code.strip(), label.strip()))
        else:
            # best-effort: whole token as label with implicit codes
            out.append((str(len(out) + 1), part))
    return out


def load_dictionary(path: str | Path) -> Dictionary:
    """Load a REDCap dictionary CSV into normalized structures.

    Keeps raw rows for reference and extracts parsed fields, including choices
    and matrix groupings.
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]

    fields: List[DictField] = []
    by_var: Dict[str, DictField] = {}
    matrix_groups: Dict[str, List[str]] = defaultdict(list)

    for r in rows:
        variable = r.get("variable_name", "").strip()
        if not variable:
            continue
        field_type = (r.get("field_type", "") or "").strip()
        choices = _parse_choices(field_type, r.get("choices_calculations_or_slider_labels", ""))
        validation = (r.get("text_validation_type_or_show_slider_number", "") or "").strip()
        vmin = (r.get("text_validation_min") or None)
        vmax = (r.get("text_validation_max") or None)
        identifier = (r.get("identifier", "") or "").strip().lower() == "y"
        required = (r.get("required_field", "") or "").strip().lower() == "y"
        branching = (r.get("branching_logic", "") or "").strip()
        matrix = (r.get("matrix_group_name", "") or "").strip()
        field = DictField(
            variable=variable,
            form_name=(r.get("form_name", "") or "").strip(),
            field_type=field_type,
            field_label=(r.get("field_label", "") or "").strip(),
            choices=choices,
            validation=validation,
            vmin=vmin,
            vmax=vmax,
            identifier=identifier,
            required=required,
            branching_logic=branching,
            matrix_group=matrix,
            raw=r,
        )
        fields.append(field)
        by_var[variable] = field
        if matrix:
            matrix_groups[matrix].append(variable)

    return Dictionary(fields=fields, by_var=by_var, choices={f.variable: f.choices for f in fields}, matrix_groups=matrix_groups)


def load_dataset_headers(path: str | Path) -> List[str]:
    """Read only the header row from a CSV dataset."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return []
    return headers


def iter_dataset_rows(path: str | Path) -> Iterable[Dict[str, str]]:
    """Stream dataset rows as dicts (CSV)."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            yield r


_ymd = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_mdy = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def is_int(s: str) -> bool:
    try:
        int(s)
        return True
    except Exception:
        return False


def is_num(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False


def is_date_ymd(s: str) -> bool:
    return bool(_ymd.match(s))


def guess_date_format(s: str) -> str:
    if _mdy.match(s):
        return "date_mdy"
    if _ymd.match(s):
        return "date_ymd"
    return "string"
