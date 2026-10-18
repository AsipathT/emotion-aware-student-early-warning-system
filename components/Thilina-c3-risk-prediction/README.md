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
