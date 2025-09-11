# DD-Val: REDCap Eval Corpus + Scoring

## Overview

This repo provides deterministic, programmatic tooling to build a REDCap-only evaluation corpus and score a validator’s findings against a gold standard. It is meant to exercise a separate validator CLI you bring (e.g., your `dd-val`), not to perform validation itself.

What you get:
- Reproducible clean REDCap projects (dictionary.csv + dataset.csv)
- Perturbed variants with controlled error recipes and gold.json ground truth
- A pluggable runner to execute your validator across the corpus
- A scorer to compute per-issue precision/recall/F1

## Requirements

- Python 3.9+
- uv (recommended) for running commands: https://docs.astral.sh/uv/
- No external Python dependencies required

## Quick Start (uv)

Seed a corpus (10 projects × 500 rows):

```bash
uv run dd-seed --out corpus --projects 10 --rows 500 --seed 42
```

Run the included validator across clean and perturbed sets:

```bash
VALIDATOR_CMD='uv run dd-val --dict {dict} --data {data} --out {out} --html {html}' \
  scripts/validate_all.sh

Noise gate for clean runs (optional):

```bash
CLEAN_STRICT=1 VALIDATOR_CMD='uv run dd-val --dict {dict} --data {data} --out {out} --html {html}' \
  scripts/validate_all.sh
```
This fails the run if any clean project emits an error finding (warnings are reported but do not fail).
```

Score your findings against the gold truth:

```bash
uv run dd-score --corpus corpus --mode variable
```

Make targets (convenience):

```bash
make seed       # uv run dd-seed …
make validate   # scripts/validate_all.sh using $VALIDATOR_CMD
make score      # uv run dd-score …
```

## CLI Commands

- `dd-seed`: Generate clean + perturbed corpora.
  - `--out`: Output directory (default: `corpus`)
  - `--projects`: Number of projects (default: `10`)
  - `--rows`: Rows per project (default: `500`)
  - `--seed`: RNG seed (default: `42`)

- `dd-val`: Validate a dataset against a dictionary and produce `report.html` and `findings.json`.
  - `--dict`: Path to dictionary CSV
  - `--data`: Path to dataset CSV
  - `--out`: Output findings.json path
  - `--html`: Output HTML report path
  - `--prev`: Optional previous findings.json to emit “since last run” diffs

- `scripts/validate_all.sh`: Run your validator on each perturbed project.
  - Set `VALIDATOR_CMD` with placeholders: `{dict} {data} {out} {html}`
  - Example: `VALIDATOR_CMD='dd-val --dict {dict} --data {data} --out {out} --html {html}'`
  - Produces per-project `findings.json` and `report.html` alongside inputs

- `dd-score`: Compare `findings.json` vs `gold.json` across the corpus.
  - `--corpus`: Corpus directory (default: `corpus`)
  - `--mode`: Matching mode: `variable` (type+variable) or `strict` (type+variable+expected/observed)

## Corpus Layout

```
corpus/
  proj01_clean/
    dictionary.csv
    dataset.csv
  proj01_perturbed/
    dictionary.csv
    dataset.csv
    gold.json
  proj01_perturbed_v2/
    dictionary.csv     # may differ from perturbed
    dataset.csv        # since-last-run changes
    gold.json          # union of v1 + v2 changes
  …
```

## Error Recipes (gold truth)

Perturbations are deterministic with the seed and include:
- Missing/extra columns (data vs. dictionary)
- Type drift (numeric → string; date_ymd → date_mdy subset)
- Domain drift (unseen categorical levels)
- Unit anomalies (subset looks like unit-converted values)
- Missingness spikes (structured blanks)
- Rename drift (e.g., `bp_sys` → `sbp` in data)
- Checkbox expansion mismatch (`var___code` differences)
- Branching mismatch (values appearing outside logic)
- Matrix break (non-consecutive dictionary rows)
- Since-last-run: new categories/columns in v2

Each injected issue is logged in `gold.json` as a compact record, e.g.:

```json
{"type":"domain_mismatch","variable":"sex","expected":["0=Male","1=Female"],"observed":["0","1","9"],"rows_affected":20}
```

## Notes

- Clean datasets strictly conform to their `dictionary.csv` (REDCap A–R headers).
- Checkbox fields expand to `var___code` columns in `dataset.csv`.
- Use `--seed` to keep runs fully reproducible.
- Bring your own validator CLI; this repo focuses on corpus + scoring.
