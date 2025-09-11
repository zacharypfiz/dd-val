from __future__ import annotations

"""Synthesize small, realistic REDCap dictionaries and conforming datasets."""

import random
from datetime import date, timedelta
from typing import Dict, List, Tuple

from .schema import HEADERS, empty_row, normalize_row
from .util import rnd_choice


def _dd_row(**kwargs) -> Dict[str, str]:
    row = empty_row()
    for k, v in kwargs.items():
        row[k] = v
    return row


def _choices_str(pairs: List[Tuple[str, str]]) -> str:
    return " | ".join([f"{v},{lbl}" for v, lbl in pairs])


def build_dictionary(project_idx: int, rng: random.Random) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    # Forms
    form1 = "enrollment"
    form2 = "followup"

    # Section headers
    sec_demo = "Demographics"
    sec_vitals = "Vitals"
    sec_follow = "Follow-up"

    # Record ID
    rows.append(
        _dd_row(
            variable_name="record_id",
            form_name=form1,
            section_header=sec_demo,
            field_type="text",
            field_label="Record ID",
            text_validation_type_or_show_slider_number="integer",
            identifier="y",
            required_field="y",
        )
    )

    # Sex radio
    sex_choices = [("0", "Male"), ("1", "Female")]
    rows.append(
        _dd_row(
            variable_name="sex",
            form_name=form1,
            field_type="radio",
            field_label="Sex at birth",
            choices_calculations_or_slider_labels=_choices_str(sex_choices),
            required_field="y",
        )
    )

    # Pregnant (branching on sex == 1)
    rows.append(
        _dd_row(
            variable_name="pregnant",
            form_name=form1,
            field_type="yesno",
            field_label="Currently pregnant?",
            branching_logic="[sex] = '1'",
        )
    )

    # Age
    rows.append(
        _dd_row(
            variable_name="age",
            form_name=form1,
            field_type="text",
            field_label="Age (years)",
            text_validation_type_or_show_slider_number="integer",
            text_validation_min="0",
            text_validation_max="120",
            required_field="y",
        )
    )

    # Height (cm), Weight (kg)
    rows.append(
        _dd_row(
            variable_name="height_cm",
            form_name=form1,
            field_type="text",
            field_label="Height (cm)",
            field_note="units=cm",
            text_validation_type_or_show_slider_number="number",
            text_validation_min="50",
            text_validation_max="250",
        )
    )
    rows.append(
        _dd_row(
            variable_name="weight_kg",
            form_name=form1,
            field_type="text",
            field_label="Weight (kg)",
            field_note="units=kg",
            text_validation_type_or_show_slider_number="number",
            text_validation_min="2",
            text_validation_max="400",
        )
    )

    # BMI calc
    rows.append(
        _dd_row(
            variable_name="bmi",
            form_name=form1,
            field_type="calc",
            field_label="BMI",
            choices_calculations_or_slider_labels="([weight_kg]/(( [height_cm]/100)^(2)))",
        )
    )

    # Symptoms (checkbox)
    symp_choices = [("1", "Cough"), ("2", "Fever"), ("3", "Fatigue")]
    rows.append(
        _dd_row(
            variable_name="symptoms",
            form_name=form1,
            field_type="checkbox",
            field_label="Symptoms",
            choices_calculations_or_slider_labels=_choices_str(symp_choices),
        )
    )

    # Satisfaction (dropdown Likert)
    sat_choices = [("1", "Poor"), ("2", "Fair"), ("3", "Good"), ("4", "Excellent")]
    rows.append(
        _dd_row(
            variable_name="satisfaction",
            form_name=form2,
            section_header=sec_follow,
            field_type="dropdown",
            field_label="Overall satisfaction",
            choices_calculations_or_slider_labels=_choices_str(sat_choices),
        )
    )

    # Visit dates
    rows.append(
        _dd_row(
            variable_name="visit_date_v1",
            form_name=form1,
            field_type="text",
            field_label="Visit 1 date",
            text_validation_type_or_show_slider_number="date_ymd",
        )
    )
    rows.append(
        _dd_row(
            variable_name="visit_date_v2",
            form_name=form2,
            field_type="text",
            field_label="Visit 2 date",
            text_validation_type_or_show_slider_number="date_ymd",
        )
    )

    # Matrix group: ADLs (radio yes/no)
    adl_choices = [("0", "No"), ("1", "Yes")]
    for var, label in (
        ("adls_wash", "Able to wash"),
        ("adls_dress", "Able to dress"),
        ("adls_eat", "Able to eat"),
    ):
        rows.append(
            _dd_row(
                variable_name=var,
                form_name=form1,
                field_type="radio",
                field_label=label,
                choices_calculations_or_slider_labels=_choices_str(adl_choices),
                matrix_group_name="adls",
            )
        )

    # Notes
    rows.append(
        _dd_row(
            variable_name="notes",
            form_name=form2,
            field_type="notes",
            field_label="Free-text notes",
        )
    )

    # Optional slider
    if rng.random() < 0.5:
        rows.append(
            _dd_row(
                variable_name="pain_severity",
                form_name=form2,
                field_type="slider",
                field_label="Pain severity",
                choices_calculations_or_slider_labels="0,No pain | 50,Moderate | 100,Severe",
                text_validation_type_or_show_slider_number="y",
            )
        )

    # Optional blood pressure fields
    if rng.random() < 0.7:
        rows.append(
            _dd_row(
                variable_name="bp_sys",
                form_name=form1,
                field_type="text",
                field_label="Systolic BP (mmHg)",
                field_note="units=mmHg",
                text_validation_type_or_show_slider_number="integer",
                text_validation_min="60",
                text_validation_max="260",
            )
        )
        rows.append(
            _dd_row(
                variable_name="bp_dia",
                form_name=form1,
                field_type="text",
                field_label="Diastolic BP (mmHg)",
                field_note="units=mmHg",
                text_validation_type_or_show_slider_number="integer",
                text_validation_min="30",
                text_validation_max="180",
            )
        )

    # Normalize all rows
    return [normalize_row(r) for r in rows]


def _rand_date(rng: random.Random, base: date = date(2024, 1, 1)) -> str:
    delta = timedelta(days=rng.randrange(0, 365))
    return (base + delta).isoformat()


def generate_dataset(dict_rows: List[Dict[str, str]], n: int, rng: random.Random) -> List[Dict[str, str]]:
    """Generate a dataset that conforms to the given dictionary.
    - checkbox fields expand into var___code columns of 0/1
    - calc fields are computed when possible (bmi)
    - branching_logic is respected (e.g., pregnant only for sex='1')
    """
    # Preprocess dictionary
    fields = [r["variable_name"] for r in dict_rows]
    types = {r["variable_name"]: r["field_type"] for r in dict_rows}
    choices = {}
    for r in dict_rows:
        ft = r["field_type"]
        if ft in {"radio", "dropdown", "checkbox", "yesno", "truefalse"}:
            raw = r["choices_calculations_or_slider_labels"].strip()
            pairs: List[Tuple[str, str]] = []
            if ft in {"yesno", "truefalse"}:
                # REDCap built-ins
                pairs = [("0", "No"), ("1", "Yes")] if ft == "yesno" else [("0", "False"), ("1", "True")]
            else:
                for part in raw.split("|") if raw else []:
                    part = part.strip()
                    if not part:
                        continue
                    if "," in part:
                        v, lbl = part.split(",", 1)
                        pairs.append((v.strip(), lbl.strip()))
            choices[r["variable_name"]] = pairs

    # Build dataset columns
    data_cols: List[str] = []
    for r in dict_rows:
        v = r["variable_name"]
        ft = r["field_type"]
        if ft == "checkbox":
            for code, _ in choices.get(v, []):
                data_cols.append(f"{v}___{code}")
        else:
            data_cols.append(v)

    # Generate rows
    rows: List[Dict[str, str]] = []
    for i in range(n):
        row: Dict[str, str] = {c: "" for c in data_cols}
        # record_id
        if "record_id" in data_cols:
            row["record_id"] = str(1000 + i)
        # sex
        sex_val = rnd_choice(rng, ["0", "1"]) if "sex" in types else ""
        if "sex" in data_cols:
            row["sex"] = sex_val
        # age
        if "age" in data_cols:
            row["age"] = str(rng.randrange(18, 90))
        # height/weight
        has_height = "height_cm" in data_cols
        has_weight = "weight_kg" in data_cols
        h_cm = rng.uniform(150, 190) if has_height else None
        w_kg = rng.uniform(50, 100) if has_weight else None
        if has_height:
            row["height_cm"] = f"{h_cm:.1f}"
        if has_weight:
            row["weight_kg"] = f"{w_kg:.1f}"
        # bmi
        if "bmi" in data_cols and h_cm and w_kg:
            bmi = w_kg / ((h_cm / 100) ** 2)
            row["bmi"] = f"{bmi:.1f}"
        # checkbox symptoms
        if any(c.startswith("symptoms___") for c in data_cols):
            for code, _lbl in choices.get("symptoms", []):
                row[f"symptoms___{code}"] = "1" if rng.random() < 0.3 else "0"
        # pregnant depends on sex
        if "pregnant" in data_cols:
            row["pregnant"] = ("1" if sex_val == "1" and rng.random() < 0.1 else "0") if sex_val else ""
        # dates
        if "visit_date_v1" in data_cols:
            row["visit_date_v1"] = _rand_date(rng)
        if "visit_date_v2" in data_cols:
            row["visit_date_v2"] = _rand_date(rng)
        # satisfaction
        if "satisfaction" in data_cols:
            row["satisfaction"] = rnd_choice(rng, ["1", "2", "3", "4"]) if rng.random() < 0.98 else ""
        # bp
        if "bp_sys" in data_cols:
            row["bp_sys"] = str(rng.randrange(90, 180))
        if "bp_dia" in data_cols:
            row["bp_dia"] = str(rng.randrange(50, 110))
        # notes
        if "notes" in data_cols:
            row["notes"] = "" if rng.random() < 0.6 else "Needs follow-up"
        # slider
        if "pain_severity" in data_cols:
            row["pain_severity"] = str(rng.randrange(0, 101))

        # ADLs
        for v in ("adls_wash", "adls_dress", "adls_eat"):
            if v in data_cols:
                row[v] = rnd_choice(rng, ["0", "1"]) if rng.random() < 0.95 else ""

        rows.append(row)

    return rows


def dictionary_and_data(project_idx: int, n: int, seed: int) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    rng = random.Random(seed + project_idx)
    d = build_dictionary(project_idx, rng)
    data = generate_dataset(d, n, rng)
    return d, data


def dataset_headers(dict_rows: List[Dict[str, str]]) -> List[str]:
    cols: List[str] = []
    for r in dict_rows:
        ft = r["field_type"]
        v = r["variable_name"]
        if ft == "checkbox":
            raw = r["choices_calculations_or_slider_labels"].strip()
            pairs: List[Tuple[str, str]] = []
            for part in raw.split("|") if raw else []:
                part = part.strip()
                if not part:
                    continue
                if "," in part:
                    code, _lbl = part.split(",", 1)
                    pairs.append((code.strip(), _lbl.strip()))
            for code, _ in pairs:
                cols.append(f"{v}___{code}")
        else:
            cols.append(v)
    return cols
