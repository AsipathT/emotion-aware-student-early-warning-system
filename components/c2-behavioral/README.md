# Component 2: Behavioral Engagement Trajectory (c2-behavioral)

Part of research project **J26-IT-349**.

## Purpose

Component 2 analyzes student clickstream interactions from the Open University Learning Analytics Dataset (OULAD) and LMS telemetry. It classifies weekly longitudinal engagement trajectories for each student (`(code_module, code_presentation, id_student, week_index)`) into four trajectory states:
- `stable`
- `improving`
- `declining`
- `volatile`

The component will later serve classifications via FastAPI, consuming `GET /api/v1/export/behavior` from the LMS and submitting predictions to `POST /api/v1/ingest/trajectory`.

## Folder Layout

```text
components/c2-behavioral/
├── data/              # OULAD dataset files (git-ignored, never committed)
├── docs/              # Label specification and interface notes
│   └── label_spec.md
├── models/            # Serialized model artifacts (git-ignored)
├── reports/
│   ├── figures/       # EDA and evaluation figures (git-ignored)
│   └── metrics/       # Audit metrics and evaluation results
├── scripts/           # Auditing and utility scripts
│   └── audit_oulad.py
├── src/               # Shared logic, configurations, and models
│   ├── __init__.py
│   └── config.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup & Dataset Configuration

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Download the OULAD dataset (7 CSV files) from [https://analyse.kmi.open.ac.uk/open_dataset](https://analyse.kmi.open.ac.uk/open_dataset) into a local folder (e.g. `C:\Datasets\OULAD`).

3. Set the `OULAD_DIR` environment variable in PowerShell:
   ```powershell
   $env:OULAD_DIR="C:\path\to\oulad_folder"
   ```

## Running the Data Audit

From the `components/c2-behavioral/` directory:

```powershell
python scripts/audit_oulad.py
```

This validates dataset presence, inspects distributions, computes trajectory labeling prerequisites, prints a readable console summary, and saves metrics to `reports/metrics/data_audit.json`.
