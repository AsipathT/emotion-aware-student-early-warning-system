# C3 Multimodal Risk Prediction Architecture

## 1. Input Features
1. **Affective Distress Features (from C1)**:
   - `exam_anxiety`
   - `conceptual_confusion`
   - `academic_helplessness`
   - `course_frustration`
   - `motivation_erosion`
   - `stress_label`
   - `confidence`

2. **Longitudinal Behavioral Velocity (from C2)**:
   - `trajectory_label` (`stable`, `improving`, `declining`, `volatile`)
   - LMS clickstream counts, active days, video watch minutes, assignment submission lateness.

3. **Academic Performance (LMS)**:
   - Quiz average, assignment scores, cumulative grade point trend, attendance rate.

## 2. Model Pipeline
- Data preprocessing & imputation
- Multimodal feature fusion
- Ensemble risk classifier / regressor (XGBoost, LightGBM, Random Forest)
- SHAP TreeExplainer for local feature attribution (`top_drivers` & `modality_contributions`)

## 3. Delivery
- Generates JSON payload matching `RiskAssessment` contract
- Ingested by Platform via `POST /api/v1/ingest/risk`
