DD-Val — REDCap Validator Technical Spec (v1)
0) Elevator pitch

Input: REDCap Data Dictionary CSV/XLSX (Columns A–R) + dataset CSV/Parquet (REDCap export).
Output: report.html (human-readable) + findings.json (machine-readable) + optional “since last run” diff if -prev given.
Goal: Detect dictionary ambiguity and schema drift with ≥90% detection accuracy, ≤10s runtime on 100k×500.

1) Supported inputs
1.1 Data Dictionary (required)

Formats: .csv (canonical), .xlsx (converted to CSV internally).

Columns (A–R):
variable_name, form_name, section_header, field_type, field_label, choices_calculations_or_slider_labels, field_note, text_validation_type_or_show_slider_number, text_validation_min, text_validation_max, identifier, branching_logic, required_field, custom_alignment, question_number, matrix_group_name, matrix_ranking, field_annotation

Minimal required per field: A (variable_name), B (form_name), D (field_type), E (field_label).

Required for categorical: F (choices).

Optional but parsed: H/I/J (validation + min/max), K (identifier), L (branching), P/Q (matrix).

1.2 Dataset (required)

Formats: .csv, .parquet (Arrow).

Assumption: Wide table; columns match dictionary variable names (checkboxes may be expanded as var___code).

1.3 Previous findings (optional)

-prev: a prior findings.json to power “Since Last Run”.

2) Normalization layer
2.1 Dictionary normalization

Field types (enum): text, notes, radio, dropdown, checkbox, calc, file, yesno, truefalse, descriptive, slider.

Text validations (enum): date_mdy, date_ymd, date_dmy, datetime_*, datetime_seconds_*, integer, number, email, phone, time, zipcode, letters, mrn (accept superset).

Choices: parse Column F into [(code, label)] using | separator; trim whitespace; keep original code strings (no coercion yet).

Checkbox expansion model: a checkbox field with choices {1,2,3} implies dataset columns name___1, name___2, name___3 storing 0/1.

Yes/No, True/False: treat as categorical with fixed codes (0/1).

Matrix: group by matrix_group_name; store field order (consecutive check later).

Booleans: K/M/Q accept y or blank only.

2.2 Dataset normalization

Column names: exact string match; case-sensitive.

Whitespace: trim leading/trailing in values (not column names).

Missing: treat "" and empty as NA; configurable later.

Type inference (lightweight):

Try integer → number → date/datetime (based on validation) → string.

Keep counters of parse successes/failures for each type.

3) Validation rules (checks)

Each check yields findings with: id, type, severity, variable, evidence, suggestion, where, and optional examples (up to 5 raw examples).

3.1 Conformance to dictionary (Spec ↔ Data Diff)

Severity scale: error (blocks analysis) | warn (nice-to-fix) | info (context).

Missing column (error): field in dictionary not present in dataset.

For checkbox: flag each missing var___code.

Evidence: field name(s). Suggestion: add or update export; confirm form/event.

Unexpected column (warn): dataset column not in dictionary.

Skip REDCap system columns (e.g., record_id if not listed? configurable).

Suggestion: add to dictionary or remove from export.

Type mismatch (error for strict text validations; else warn):

If dictionary field_type=text with validation=integer/number/date*, compute parse success rate; if <95% → error with examples.

If categorical (radio/dropdown/yesno/truefalse), non-code values present → error.

Domain mismatch (error): observed category not in choices.

Case/whitespace normalized comparison first; store raw examples.

For yesno/truefalse, only {0,1} allowed.

Checkbox conformance (error): dataset has var___k for a code not in dictionary; or allowed code missing in dataset with non-NA values present elsewhere.

Validation min/max violations (warn): for numeric/date validations, % outside min/max > threshold (default 1%). Include min/max and example values.

Unit hint (warn): numeric distribution suggests alternate unit (e.g., heights with median < 3 if cm expected). Heuristic only; provide rationale.

Matrix non-consecutive rows (warn): fields with same matrix_group_name are not in consecutive rows of dictionary.

Branching logic sanity (info): optional lightweight parse; ensure referenced variables exist; do not evaluate logic in v1.

Identifier flagging (info): possible PHI names (name, email, etc.) not marked identifier=y. (Dictionary hygiene helper.)

3.2 Dictionary completeness score (ambiguity)

Score (%) = mean over fields of required metadata present:

label (E), type (D), choices for categorical (F), validation for text (H if applicable), identifier flag set for likely PHI (K), min/max when validation is numeric/date (I/J).

Also list top missing elements (e.g., “14 fields missing choices”).

3.3 “Since last run” (schema drift)

Given previous findings.json:

New columns, removed columns.

Type changes, new categories observed per variable.

Changes in dictionary (e.g., choices modified).
Output a concise changelog section + diff block in JSON.

4) Algorithms & thresholds

Parsing choices (F): split by |, each token code, label. Permit commas in labels if quoted? (v1: assume not; fail gracefully with a finding if malformed).

Type inference per column: sample up to 50k values; attempt parse; compute success ratio. Thresholds:

Integer: ≥99% ints → integer;

Number: ≥99% numeric → number;

Date/datetime: ≥95% parse under specified format; else mismatch.

Domain check: map dataset values to strings; normalize by trimming and casefold; compare to dictionary code (string match). Keep raw examples.

Min/max violation: flag if >1% beyond bounds (configurable), include tail stats.

Unit hint: simple rules (e.g., height median < 3 and > 0.25 → “meters?”, while dictionary says cm; BMI out of plausible 8–80 → hint). These are warn only.

5) Output formats
5.1 report.html (single page)

Header: dataset path, dictionary path, timestamp, rows/cols, Dictionary Completeness Score.

A. Must-fix (errors): missing columns, type/domain mismatches, bad checkbox expansions. Each item shows variable, description, and up to 5 examples.

B. Nice-to-fix (warnings): unexpected columns, min/max violations, unit hints, matrix non-consecutive.

C. Since last run: concise changelog (if -prev).

D. Query Pack (copy-paste): grouped by variable, succinct questions:

“sex: Observed values {‘M’,’female’} not in allowed codes {0,1}. Should ‘M/female’ map to 0/1, or be coded missing?”

“bp_sys: 4.2% of values < 50 or > 260 (min/max). Confirm bounds or update dictionary I/J.”

Footer: DD-Val version, config knobs used.

5.2 findings.json (machine-readable)

Schema (per finding):

{
  "id": "F-000123",
  "type": "domain_mismatch|missing_column|type_mismatch|...",
  "severity": "error|warn|info",
  "variable": "sex",
  "where": {"dataset_column": "sex"},
  "expected": {"codes": ["0","1"], "validation": "integer"},
  "observed": {"unexpected_values": ["M","female"], "n_rows": 87},
  "examples": ["M","female"],
  "suggestion": "Map 'M'/'female' to allowed codes or revise choices in Column F.",
  "context": {"form_name": "demographics", "field_type": "radio"}
}


Also include a top-level summary:

{
  "summary": {"rows": 18234, "cols": 143, "dict_fields": 137, "score_completeness": 0.86},
  "findings": [ ... ]
}

6) CLI & configuration
6.1 CLI
ddval --dict path/to/dictionary.csv \
      --data path/to/export.csv \
      --prev path/to/old/findings.json \
      --out path/to/report.html \
      [--findings path/to/findings.json] \
      [--strict] [--sample 50000] [--domain-case-insensitive true]

6.2 Config (defaults shown)

strict=false (promote certain warns to errors if true).

domain.case_insensitive=true, domain.trim_whitespace=true.

type.integer_success>=0.99, type.number_success>=0.99, type.date_success>=0.95.

minmax.violation_threshold=0.01 (1%).

examples.max=5, sample.max_rows=50000.

7) Performance & accuracy targets

Runtime: ≤10s on 100k rows × 500 cols, CSV input, using vectorized ops (pandas/pyarrow) and reservoir sampling for type checks.

Memory: Stream CSV when possible; avoid full string copies.

Accuracy:

Detect ≥90% of seeded issues across: missing/extra columns, type mismatches, domain mismatches, min/max, checkbox conformance, matrix ordering.

≤1 false positive per standard project (10–60 vars).

8) Testing & evaluation
8.1 Corpus layout
/corpus
  /proj01_clean/{dictionary.csv,dataset.csv}
  /proj01_perturbed/{dictionary.csv,dataset.csv,gold.json}
  /proj01_perturbed_v2/{dictionary.csv,dataset.csv,gold.json}
  ...

8.2 Deterministic corruption recipes

Missing/extra columns, rename drift, type drift, domain drift (case/whitespace/synonyms), min/max violations, checkbox expansion issues, matrix non-consecutive, “since last run” new categories/columns.

8.3 Scorer

Compare findings.json to gold.json; compute precision/recall/F1 by issue type. Fail CI if thresholds not met.

9) Security & privacy

Local-only. No network calls.

No data persistence beyond outputs to specified paths.

Redaction in report: examples truncate long strings; never display >5 row examples per issue.

PHI handling: flag likely identifiers; do not export raw values for those fields unless --allow-phi-examples.

10) Extensibility (post-MVP hooks)

Emit validators: generate Pandera schema (Python) or R checks from accepted dictionary.

Adapters: generic dictionary schema; later OMOP/CDISC adapters.

UI shell: optional later (serve report.html), but not in MVP.

11) “What good looks like” (acceptance)

Run:

ddval --dict corpus/proj01_perturbed/dictionary.csv \
      --data corpus/proj01_perturbed/dataset.csv \
      --prev corpus/proj01_clean/findings.json \
      --out out/report.html --findings out/findings.json


Produces:

report.html with Score, Must-fix, Nice-to-fix, Since last run, Query Pack.

findings.json matching gold.json with ≥0.90 F1 overall.

Wall-time ≤10s on stress case.

12) Query Pack phrasing templates (MVP)

Missing column:
“{var} is defined in the dictionary (Form {form}) but missing from the dataset. Should this field be included in the next export, or removed from the dictionary?”

Unexpected column:
“Dataset contains column {col} not present in the dictionary. Should we add it to the dictionary or exclude it from analysis?”

Domain mismatch:
“{var} observed values {{observed[:5]}…} are not in allowed codes {{expected}}. How should we map these (or should they be treated as missing)?”

Type mismatch:
“{var} is validated as {validation} but {fail_pct}% of values do not parse (e.g., {examples}). Should the validation change or the data be recoded?”

Min/Max:
“{var} has {viol_pct}% values outside [{min}, {max}] (e.g., {examples}). Confirm bounds or update dictionary.”

13) Implementation notes

Stack: Python 3.11+, pandas + pyarrow; Jinja2 for HTML; or Go/Rust if you prefer a single static binary later.

HTML: build a clean, single CSS file; no external fonts/CDNs (offline friendly).

Internationalization: not required in v1; keep formats ISO where possible (dates shown as observed).

Logging: write a terse CLI log to stderr; --verbose shows timing per check.