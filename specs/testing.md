# Testing Strategy: Data Dictionary Validator (DD-Val)

## 1. Guiding Principle

DD-Val will be rigorously tested and validated **without using any private or protected data**.

Our strategy relies on a reproducible **test corpus** composed of two data sources:

1. **Public Datasets** with existing, high-quality codebooks.
2. **Synthetic Datasets** that are deterministically corrupted to mimic common real-world errors.

This approach allows us to objectively measure the tool's accuracy (precision/recall) and performance against a known ground truth.

## 2. Test Corpus Structure

The repository will contain a `/corpus` directory with multiple test projects. Each project will have a clean version and a perturbed (corrupted) version.

`/corpus
  /project_01_clean/
    dataset.csv
    dictionary.csv
  /project_01_perturbed/
    dataset.csv
    dictionary.csv
    gold.json         # Ground-truth log of all injected errors
  /project_02_.../`

## 3. Data Sources

The test corpus will be built from:

- **Public Datasets:** Subsets from sources like **NHANES**, **BRFSS**, and **Synthea** will be used to provide realistic schemas and codebooks.
- **Synthetic Datasets:** Small, clean datasets will be programmatically generated to conform to standard formats, particularly the common **REDCap data dictionary CSV template**.

## 4. Error Injection Strategy

Errors will be injected into clean datasets using a **deterministic, rule-based script** with a fixed random seed. This ensures that our test suite is 100% reproducible. Each injected error will be logged to the project's `gold.json` file.

### Seeded Error Scenarios

The script will inject a variety of common data issues, including:

- **Missing/Extra Columns:** Asymmetry between the dictionary and the dataset.
- **Type Drift:** Mismatches between specified and actual data types (e.g., `int` vs `string`, `YYYY-MM-DD` vs `MM/DD/YYYY`).
- **Domain Drift:** The dataset contains values not listed in the dictionary's `allowed_values` (including case/whitespace variants).
- **Unit Anomalies:** A subset of numeric values are altered in a way that suggests a unit mismatch (e.g., some heights are in `cm`, others in `inches`).
- **Schema Drift:** A column is renamed in the dataset but not the dictionary.
- **REDCap Formats:** A single categorical variable is split into multi-select checkbox columns (e.g., `var___1`, `var___2`).

## 5. Evaluation and Scoring

The tool's performance will be measured objectively:

- **Accuracy:** The `findings.json` output from DD-Val will be programmatically compared against the `gold.json` ground truth to calculate **Precision, Recall, and F1 scores** for each error type.
- **Performance:** Runtime will be benchmarked against a large-scale synthetic dataset (e.g., 100k rows x 500 columns) with a target of **≤ 10 seconds** per run.
- **Regression Testing:** The fixed seed ensures the test corpus remains stable, allowing us to catch any regressions in detection capability.

## 6. Repository & Reproducibility

To ensure full transparency and reproducibility, the project repository will include:

- The complete `/corpus` of clean and perturbed test cases.
- The script to generate the perturbed datasets from the clean versions (`seed.py`).
- A script to run DD-Val across the entire corpus (`validate_all.sh`).
- The script to compare the tool's output against the ground truth and generate a performance report (`score.py`).
