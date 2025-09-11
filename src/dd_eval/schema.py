from __future__ import annotations

from typing import Dict, Iterable, List


# REDCap Data Dictionary headers (A–R)
HEADERS: List[str] = [
    "variable_name",
    "form_name",
    "section_header",
    "field_type",
    "field_label",
    "choices_calculations_or_slider_labels",
    "field_note",
    "text_validation_type_or_show_slider_number",
    "text_validation_min",
    "text_validation_max",
    "identifier",
    "branching_logic",
    "required_field",
    "custom_alignment",
    "question_number",
    "matrix_group_name",
    "matrix_ranking",
    "field_annotation",
]


FIELD_TYPES = {
    "text",
    "notes",
    "radio",
    "dropdown",
    "checkbox",
    "yesno",
    "truefalse",
    "calc",
    "slider",
}


TEXT_VALIDATIONS = {
    "integer",
    "number",
    "date_ymd",
    "date_mdy",
    "datetime_ymd",
    "email",
    "phone",
    "zipcode",
}


def empty_row() -> Dict[str, str]:
    return {h: "" for h in HEADERS}


def normalize_row(row: Dict[str, str]) -> Dict[str, str]:
    out = empty_row()
    for k, v in row.items():
        if k in out:
            out[k] = "" if v is None else str(v)
    return out


def ensure_headers(columns: Iterable[str]) -> bool:
    cols = list(columns)
    return cols == HEADERS
