### **Project Requirements Document: Data Dictionary Validator (DD-Val)**

- **Version:** 1.0
- **Date:** September 10, 2025

### **1. Problem Statement**

Biostatisticians and research analysts spend significant, unpredictable amounts of time resolving discrepancies between research datasets and their corresponding data dictionaries. This manual "back-and-forth" with study teams is driven by two primary issues: **(1)** incomplete or inaccurate dictionaries (ambiguity) and **(2)** changes to the data's structure between refreshes (schema drift). This friction delays the start of analysis, introduces risk of error, and is a major source of inefficiency.

### **2. Goal & Value Proposition**

To create a lightweight, local-first command-line tool that automates the validation of a dataset against its data dictionary. DD-Val will produce a single, actionable report that instantly identifies discrepancies and changes.

This tool will empower analysts to systematically identify all data quality issues in minutes, not hours, and provide them with a clear, auto-generated "query pack" to send to the study team for rapid resolution.

### **3. User Personas**

- **Primary User (MVP Target):** The Analyst / Biostatistician. The direct recipient of the data who feels the pain of discrepancies.
- **Secondary User (Long-Term Goal):** The Data Manager / Study Coordinator. The creator of the data who could use the tool as a "pre-flight check" before sending.

### **4. Core Features & Scope (MVP)**

The tool will execute as a single command and produce two output files. Its core function is to generate a comprehensive "State of the Data" report based on the following checks:

1. **Dictionary vs. Data Reconciliation:** Compare the dictionary specification against the dataset to identify:
   - Columns present in the dictionary but missing from the data.
   - Columns present in the data but missing from the dictionary.
   - Type mismatches (e.g., dictionary specifies `numeric`, data is `string`).
   - Domain mismatches (e.g., data contains values like `"M"`, `"female"`, or `"99"` that are not listed in the dictionary's `allowed_values`).
2. **"Since Last Run" Change Detection:** If a previous report is provided, identify and list key schema changes, including:
   - New columns added.
   - Columns removed.
   - Newly observed categories/values in existing columns.
3. **Actionable Report Generation:** Produce two key outputs:
   - A single, human-readable **HTML report** summarizing all findings.
   - An auto-generated, copy-pasteable **"Query Pack"** within the report that lists clear, concise questions for the study team to resolve.
   - A machine-readable **`findings.json`** file detailing all issues, to be used as the input for the "Since Last Run" feature.

### **5. Inputs & Outputs**

- **Inputs:**
  - `-dict`: Path to the data dictionary file (`.csv`, `.xlsx`).
  - `-data`: Path to the dataset file (`.csv`, `.parquet`).
  - `-prev` (Optional): Path to a previous `findings.json` output file.
- **Outputs:**
  - `report.html`: The human-readable validation report.
  - `findings.json`: The machine-readable list of all findings.

### **6. Non-Functional Requirements**

- **Execution Environment:** Must run as a local-first Command-Line Interface (CLI) tool. No server, database, or user authentication is required for the MVP.
- **Performance:** End-to-end run time must be **≤ 10 seconds** on a typical laptop for a dataset up to 100,000 rows and 500 columns.
- **Accuracy:** Must correctly identify ≥90% of seeded errors with ≤1 false positive on a standardized test dataset.

### **7. Out of Scope (for MVP)**

The following features will not be included in the initial version to ensure a tight scope and fast delivery:

- Graphical User Interface (GUI).
- User accounts, team projects, or collaboration features.
- Mapping to external ontologies (e.g., LOINC, SNOMED).
- Data visualization or charting.
- Direct, bidirectional editing of the data dictionary file.

### **8. Success Metrics**

The success of the DD-Val prototype will be measured by its ability to:

- **Quantitative:** Reduce the time-to-first-analysis by catching all data quality issues in a single, automated pass. Success is measured by the number of back-and-forth email threads avoided.
- **Qualitative:** Receive positive feedback from pilot users (e.g., "This would have saved me a week on my last project").
- **Adoption:** Pilot users run the tool on every single data refresh, demonstrating that the "Since Last Run" feature provides ongoing value.
