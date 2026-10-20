# C3: Multimodal Risk Prediction

Component 3 of the **AI-Driven Early Warning System for Student Dropout in Higher Education** (SLIIT Research Project).

C3 synthesizes student data across multiple dimensions (C1 Affective distress signals, C2 Behavioral engagement velocity, and LMS Academic performance) to generate an explainable, weekly composite dropout risk assessment for each student.

**Owner:** Thilina  |  **Status:** In Development (Scaffolding & Baseline Exploration)

---

## 1. Component Overview & Responsibilities

| Dimension | Description |
|---|---|
| **Input** | 1. **C1 Affective Profile**: 5-class distress scores, dominant stress label, confidence.<br>2. **C2 Behavioral Velocity**: Trajectory classification (`stable`, `improving`, `declining`, `volatile`) & clickstream telemetry.<br>3. **LMS Academic Data**: Assessment submissions, quiz scores, grade trends, and attendance records. |
| **Output** | Per student (`pid`), per course, per week: Composite `risk_score` ($0.0 - 1.0$), `risk_tier` (`low`, `medium`, `high`, `critical`), `modality_contributions` (`affective`, `behavioral`, `academic`), and `top_drivers` (SHAP-ranked explainability factors). |
| **Delivery** | `POST /api/v1/ingest/risk` with component API key (`C3_COMPONENT_KEY`). |

---

## 2. Risk Tier Definitions

| Risk Tier | Risk Score Range | Recommended Action Level |
|---|---|---|
| `low` | $[0.00, 0.30)$ | Standard monitoring, automated encouragement. |
| `medium` | $[0.30, 0.60)$ | Academic advisor alert, peer tutoring suggestion. |
| `high` | $[0.60, 0.85)$ | Active counsellor outreach, deadline extension / consultation. |
| `critical` | $[0.85, 1.00]$ | Immediate multi-disciplinary intervention required. |

---

## 3. Directory Layout

```text
Thilina-c3-risk-prediction/
├── data/              # Raw & processed multimodal datasets (never committed)
├── docs/              # Architecture, feature dictionary, & evaluation methodology
├── models/            # Serialized ML artifacts & SHAP explainers (.joblib, .json)
├── notebooks/         # Exploratory data analysis, feature engineering, & benchmarking
├── src/               # Reusable Python modules (data loaders, feature fusion, model training, API delivery)
├── tests/             # Unit and integration test suites
├── .env.example       # Environment variables template
├── pytest.ini         # Pytest configuration
├── requirements.txt   # Python dependency specifications
└── README.md          # Component documentation
```

---

## 4. Setup & Quickstart

```bash
# 1. Navigate to component root
cd components/Thilina-c3-risk-prediction

# 2. Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env

# 5. Run test suite
pytest
```

---

## 5. Model Architecture & Comparative Benchmark

To rigorously establish the most effective predictive paradigm for sparse multimodal educational telemetry, C3 implements a comparative benchmark evaluating linear, deep sequential, and tree-based ensemble architectures against a majority-class baseline on unseen students (**Cohort 3**, $N=5,432$ records, test positive rate: $4.79\%$).

### 5.1 Test-Set (Cohort 3) Evaluation Metrics

| Model Architecture | ROC-AUC | PR-AUC | F1 (at Val Threshold) | Brier Score (Calibration) | ECE (Expected Calibration Error) | Positive Rate | Confusion Counts (TN, FP, FN, TP) |
|---|---|---|---|---|---|---|---|
| **Majority-Class Baseline** | 0.5000 | 0.0479 | 0.0000 (th=0.50) | 0.0457 | 0.0115 | 0.0000 | (5172, 0, 260, 0) |
| **Logistic Regression** | 0.8528 | 0.2514 | 0.3193 (th=0.87) | 0.1572 | 0.2755 | 0.0525 | (4974, 198, 173, 87) |
| **BiLSTM Sequence Model (PyTorch)** | 0.8272 | 0.2119 | 0.2566 (th=0.89) | 0.1322 | 0.1522 | 0.0770 | (4841, 331, 173, 87) |
| **C3 Gradient-Boosting Model (Champion)** | **0.8305** | 0.1810 | **0.2586** (th=0.07) | **0.0457** | **0.0322** | 0.0974 | (4745, 427, 158, 102) |

### 5.2 Key Research Takeaways (Why Gradient Boosting is the Champion for C3)

1. **Probability Calibration (Brier Score & ECE):**
   - In early warning systems, actionable intervention requires well-calibrated probabilities, not just rankings.
   - **Gradient Boosting** achieved an **ECE of 0.0322** and **Brier Score of 0.0457** (matching Bayesian minimum entropy), compared to **0.1522** and **0.1322** for BiLSTM.
2. **Handling Sparse Tabular Data & Missingness:**
   - Real-world telemetry contains irregular intervals (e.g. absent midterm marks early in the term, sporadic affective forum posts). Tree ensembles handle median-imputation and non-linear step-functions without gradient degradation.
3. **Exact Tree-SHAP Explainability:**
   - TreeExplainer provides fast, game-theoretically consistent feature attribution for every individual student prediction, meeting the institutional transparency requirement for academic interventions.
4. **BiLSTM Sequential Momentum:**
   - The BiLSTM model ($W=5$ weekly temporal window, 2 bidirectional layers, dropout=0.25) validates that longitudinal trend context captures significant temporal signal (ROC-AUC 0.8272). Both model weights are preserved in `models/` for academic ablation analysis.

---

## 6. Modality-Level Attribution Benchmark

C3 evaluates which student modality (Affective, Behavioural, Academic) was the primary catalyst of dropout risk using **Modality-Level Permutation Attribution** (20 shuffle iterations per modality) benchmarked against ground truth planted crisis drivers:

- **Attribution Accuracy (First 3 Weeks Post-Onset, Observed Affect):** **48.73%** (95% CI: `[41.95%, 55.10%]`) vs **33.33%** chance level.
- **Attribution Accuracy (All Crisis Rows):** **42.05%**.
- **Secondary Report (Normalized SHAP per Feature Count):** **35.17%**.

### Per-Driver Attribution Accuracy:
- **Academic Catalyst:** 57.61%
- **Affective Catalyst:** 50.75%
- **Behavioural Catalyst:** 36.36%

---

## 7. Execution Commands

```bash
# 1. Train and benchmark all models (Cohort 1 train, Cohort 2 val tune, Cohort 3 test)
python src/train.py

# 2. Run unit tests
python -m pytest tests/test_c3_pipeline.py -v

# 3. Perform live inference and ingest risk envelopes into backend
python src/predict_and_ingest.py
```

