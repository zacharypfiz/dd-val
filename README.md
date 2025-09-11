# Data Dictionary Validator (DD-Val)

## Overview

DD-Val is a lightweight, local-first command-line tool that automates the validation of a dataset against its data dictionary. It produces a single, actionable report that instantly identifies discrepancies and changes, empowering analysts to systematically identify all data quality issues in minutes, not hours.

## Problem Statement

Biostatisticians and research analysts spend significant, unpredictable amounts of time resolving discrepancies between research datasets and their corresponding data dictionaries. This manual "back-and-forth" with study teams is driven by two primary issues: (1) incomplete or inaccurate dictionaries (ambiguity) and (2) changes to the data's structure between refreshes (schema drift).

## Features

- **Dictionary vs. Data Reconciliation:** Identifies missing columns, extra columns, type mismatches, and domain mismatches.
- **Change Detection:** Compares against previous reports to detect schema changes.
- **Actionable Reports:** Generates HTML report and JSON findings file.
- **Query Pack:** Auto-generated questions for study teams.

## Usage

```bash
dd-val -dict <dictionary_file> -data <dataset_file> [-prev <previous_findings.json>]
```

## Inputs

- `-dict`: Path to the data dictionary file (`.csv`, `.xlsx`).
- `-data`: Path to the dataset file (`.csv`, `.parquet`).
- `-prev` (Optional): Path to a previous `findings.json` output file.

## Outputs

- `report.html`: Human-readable validation report.
- `findings.json`: Machine-readable list of findings.

## Requirements

- Python 3.x
- Dependencies: pandas, openpyxl, pyarrow (for Parquet support)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/zacharypfiz/dd-val.git
   cd dd-val
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the tool:
   ```bash
   python dd_val.py -dict dictionary.csv -data data.csv
   ```

## Development

This project is in early development. For contributions, please see the project requirements in `project.md`.

## License

[Add license here]
