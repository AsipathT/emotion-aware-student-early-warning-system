# Component 2: Behavioral Engagement Trajectory (`c2-behavioral`)

Part of research project **J26-IT-349**.

## 1. What C2 Does
Component 2 analyzes longitudinal clickstream telemetry and assessment interaction patterns to classify each student's weekly behavioral engagement trend into one of four trajectory states: `stable`, `improving`, `declining`, or `volatile`. By evaluating causal weekly histories without peeking into future activity, it delivers early warning indicators and calibrated confidence estimates to the learning management system.

---

## 2. Folder Map

```text
components/c2-behavioral/
├── data/                  # Intermediate feature datasets and sample JSON contracts
├── docs/                  # Label specifications and integration documentation
│   ├── DEMO.md            # Numbered live demo script and fallback workflows
│   └── label_spec.md      # Frozen trajectory labeling rules and definitions
├── models/                # Serialized model bundles (c2_deploy.joblib)
├── reports/
│   ├── figures/           # Visual evaluation figures (Fig 1-4)
│   ├── metrics/           # Evaluation metrics, ablation, and quantiles (JSON)
│   └── samples/           # Sample contract payload fixtures
├── scripts/               # Pipeline execution, evaluation, and reporting scripts
│   ├── ablation_evidence.py
│   ├── audit_oulad.py
│   ├── build_dataset.py
│   ├── deploy_eval.py
│   ├── export_samples.py
│   ├── label_report.py
│   ├── make_classify_sample.py
│   ├── make_figures.py
│   ├── run_week.py
│   └── train_eval.py
├── service/               # Standalone FastAPI service and LMS HTTP integration
│   ├── app.py             # Inference endpoints (/health, /classify)
│   ├── lms_client.py      # HTTP client for LMS export/ingest API
│   ├── pipeline.py        # Grouping and batch inference pipeline
│   ├── schemas.py         # Pydantic v2 data contract schemas
│   └── settings.py        # Service runtime configuration
├── src/                   # Core algorithmic and feature extraction library
│   ├── baselines.py       # Static and rule-based baseline implementations
│   ├── config.py          # Core system constants and frozen thresholds
│   ├── deploy_features.py # Scale-free deployment feature transforms
│   ├── dormant.py         # Causal dormancy rule engine
│   ├── enrolment.py       # Enrolment tracking and censoring utilities
│   ├── evaluate.py        # Macro-F1 and per-class evaluation metrics
│   ├── features.py        # Causal historical feature engineering
│   ├── indicators.py      # Contributing behavioral driver extraction
│   ├── inference.py       # Single-history online prediction engine
│   ├── labels.py          # Offline 7-week bilateral trend labeling
│   ├── splits.py          # Leak-free presentation split generator
│   └── weekly.py          # Weekly interaction aggregation routines
├── tests/                 # Unit and integration test suite
├── pytest.ini             # Pytest discovery configuration
├── requirements.txt       # Production and inference dependencies
└── README.md              # Component documentation and runbook
```

---

## 3. Data and Label Definition

All modeling is grounded in the Open University Learning Analytics Dataset (OULAD) and verified against LMS contracts:

- **Unit of Analysis**: One record per `(code_module, code_presentation, id_student, week t)` for academic weeks $t \ge 3$, where week index $= \lfloor \text{date} / 7 \rfloor$ with pre-course days excluded ($\text{date} \ge 0$).
- **Weekly Engagement Metric**: $e_w = \log(1 + \text{clicks}_w)$, with $e_w = 0$ for non-active weeks within a student's active enrolment span.
- **Label Window**: A symmetric 7-week bilateral window ($t-3 \dots t+3$) evaluated offline within valid enrolment bounds.
- **Trend Parameters**: Computed via least-squares slope of $e_w$ over the 7-week window, and residual standard deviation (`resid_sd`) around the fitted line.
- **Frozen Classification Priority Rules**:
  1. `volatile`: `resid_sd >= 1.0` and $|\text{slope}| < 0.10$
  2. `declining`: $\text{slope} \le -0.20$
  3. `improving`: $\text{slope} \ge +0.20$
  4. `stable`: otherwise
- **Dormancy Policy**: Windows where all 7 weeks have 0 clicks are flagged as dormant (13.5% of all OULAD windows; 102,356 of 755,715). During online causal inference, students exhibiting $\ge 7$ consecutive weeks of zero activity bypass the classifier and are assigned `declining` with fixed confidence $0.86$ (reflecting an uncalibrated OULAD Fail+Withdrawn rate of 54.5%).
- **Causal Constraint**: Online feature extraction uses strictly past weeks $t-5 \dots t$.

---

## 4. Experimental Results

All reported metrics are exact values loaded directly from [reports/metrics/](reports/metrics/) and rounded to 3 decimal places.

### Model Evaluation on Unseen Test Presentations (2014J)

Evaluated across 204,607 test windows against leak-free unseen course presentations:

| Model | Val Macro-F1 | Test Macro-F1 | Test Accuracy | Declining F1 | Improving F1 | Stable F1 | Volatile F1 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Majority Baseline** | 0.137 | 0.130 | 0.351 | 0.000 | 0.000 | 0.520 | 0.000 |
| **B2 Fixed-Rule Baseline** | 0.223 | 0.228 | 0.334 | 0.477 | 0.238 | 0.197 | 0.000 |
| **B1 Static Snapshot Baseline** | 0.343 | 0.382 | 0.410 | 0.515 | 0.428 | 0.378 | 0.208 |
| **C2 Model (Full Features)** | 0.471 | 0.504 | 0.528 | 0.634 | 0.563 | 0.499 | 0.320 |
| **C2 Deploy Model (Scale-Free)** | 0.466 | 0.503 | 0.526 | 0.627 | 0.560 | 0.503 | 0.321 |

*(5-Fold Student-Grouped CV Mean Macro-F1: 0.526, Std: 0.002).*

### Feature Ablation Analysis (Test Set)

| Feature Subset | Test Macro-F1 | Declining Class F1 |
| :--- | :---: | :---: |
| **Clicks Only** | 0.501 | 0.622 |
| **Clicks + Active Days** | 0.502 | 0.627 |
| **Full (Clicks + Active Days + Submissions)** | 0.504 | 0.634 |

### Overall Prediction Confidence Quantiles (Test Set, $N = 204,607$)

| Quantile / Statistic | Value |
| :--- | :---: |
| **Minimum** | 0.255 |
| **5th Percentile (p05)** | 0.357 |
| **25th Percentile (p25)** | 0.441 |
| **50th Percentile (Median)** | 0.530 |
| **Mean** | 0.561 |
| **75th Percentile (p75)** | 0.656 |
| **95th Percentile (p95)** | 0.878 |
| **99th Percentile (p99)** | 0.989 |
| **Maximum** | 1.000 |

---

## 5. Known Limitations

- Labels come from a frozen rule on weekly log1p(clicks); the model predicts them from past weeks only; there is no human-labelled ground truth.
- Results show better performance than a static-snapshot baseline and a fixed-rule baseline on unseen OULAD presentations; the gain from submission/active-day features is small.
- Withdrawal rates inside predicted classes show no strong separation; the 7-week dormancy rule is the strongest at-risk signal in OULAD.
- OULAD has no video/login/session events, so video features are deferred to pilot LMS data. Deployed model uses clicks and submissions only.
- LMS live data has known issues being fixed (submissions bridge, login event course).

---

## 6. How to Run

### Environment Setup
Activate your Python virtual environment and set the path to your uncompressed OULAD directory:
```powershell
# In components/c2-behavioral
$env:OULAD_DIR = "C:\path\to\oulad"
```

### Reproducing Data Pipelines and Training
Execute the processing scripts in sequential order:

```powershell
# 1. Audit OULAD CSV integrity and column distributions
python scripts/audit_oulad.py

# 2. Extract weekly interaction matrices and causal windows
python scripts/build_dataset.py

# 3. Generate dataset-wide label distribution report
python scripts/label_report.py

# 4. Train HistGradientBoostingClassifier and evaluate cross-validation
python scripts/train_eval.py

# 5. Run feature ablation experiments and withdrawal evidence checks
python scripts/ablation_evidence.py

# 6. Train and evaluate online scale-free deployable model bundle
python scripts/deploy_eval.py

# 7. Generate publication figures (Fig 1-4)
python scripts/make_figures.py

# 8. Export sample contract payload fixtures
python scripts/export_samples.py

# 9. Generate classify request sample fixture
python scripts/make_classify_sample.py
```

### Running the Standalone Inference Service
Launch the standalone FastAPI inference service:
```powershell
uvicorn service.app:app --port 8100
```

### Executing Live LMS Weekly Ingestion
To classify student behavior directly against a running LMS instance:
```powershell
$env:LMS_BASE_URL = "http://localhost:8000"
$env:C2_COMPONENT_KEY = "your_preshared_api_key_at_least_24_chars"

# Dry-run execution with preview table:
python scripts/run_week.py --course-id CS101 --week 5 --send --dry-run --show

# Live database persistence:
python scripts/run_week.py --course-id CS101 --week 5 --send --no-dry-run
```

For full walkthrough instructions, see [docs/DEMO.md](docs/DEMO.md).

---

## 7. Tests

Run the pure unit test suite:
```powershell
python -m pytest tests -q
```

---

## 8. Indicator Vocabulary (12 tokens)

- `clicks_declining_trend`: Linear regression slope over recent weeks <= -0.20
- `clicks_rising_trend`: Linear regression slope over recent weeks >= +0.20
- `recent_activity_drop`: Recent difference between current and prior 3-week window <= -0.50
- `recent_activity_rise`: Recent difference between current and prior 3-week window >= +0.50
- `high_weekly_variability`: High click variability with residual standard deviation >= 1.0
- `inactive_streak`: Continuous zero-click streak of 2 or more consecutive weeks
- `frequent_zero_weeks`: Two or more zero-click weeks within the recent 6-week window
- `late_submissions`: Average assessment submission delay exceeding 24.0 hours
- `steady_activity`: Default baseline when no adverse or rising behavioral signals are triggered
- `never_active`: Complete absence of clickstream interaction across all historical weeks
- `no_activity_7w`: Inactivity streak lasting 7 or more consecutive weeks following prior engagement
- `low_activity_vs_own_history`: Recent 3-week mean clicks dropped to <= 25% of the student's prior history mean (minimum 6 weeks history)

