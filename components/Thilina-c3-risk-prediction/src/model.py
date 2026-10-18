"""
components/Thilina-c3-risk-prediction/src/model.py

C3: Multimodal Risk Prediction Model & Explainability Pipeline.
Trains an ensemble model combining Academic, Behavioral, and Affective modalities.
Calculates:
  - risk_score (0.0 to 1.0)
  - risk_tier ('low', 'medium', 'high', 'critical')
  - modality_contributions ({affective: float, behavioral: float, academic: float}) summing to 1.0
  - top_drivers (SHAP-ranked human-readable risk drivers)
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.metrics import classification_report, roc_auc_score
import shap

# Feature grouping by modality
ACADEMIC_NUMERIC = [
    "quiz_avg_score",
    "assignment_avg_score",
    "assignment_submission_delay_days",
    "attendance_percentage",
    "cumulative_grade",
]

BEHAVIORAL_NUMERIC = [
    "weekly_clicks",
    "active_days_count",
    "video_watch_minutes",
    "forum_post_count",
    "trajectory_confidence",
]

AFFECTIVE_NUMERIC = [
    "exam_anxiety",
    "conceptual_confusion",
    "academic_helplessness",
    "course_frustration",
    "motivation_erosion",
    "affective_confidence",
]

CATEGORICAL_FEATURES = [
    "trajectory_label",
    "dominant_stress_label",
]

ALL_FEATURE_COLS = (
    ACADEMIC_NUMERIC + BEHAVIORAL_NUMERIC + AFFECTIVE_NUMERIC + CATEGORICAL_FEATURES
)


def map_risk_tier(score: float) -> str:
    """Classifies risk score into contract-defined risk tier."""
    if score >= 0.85:
        return "critical"
    elif score >= 0.60:
        return "high"
    elif score >= 0.30:
        return "medium"
    return "low"


class MultimodalRiskModel:
    def __init__(self, n_estimators: int = 150, max_depth: int = 6, random_state: int = 42):
        self.random_state = random_state
        self.preprocessor = ColumnTransformer(
            transformers=[
                (
                    "num",
                    StandardScaler(),
                    ACADEMIC_NUMERIC + BEHAVIORAL_NUMERIC + AFFECTIVE_NUMERIC,
                ),
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    CATEGORICAL_FEATURES,
                ),
            ]
        )
        self.clf = GradientBoostingClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=0.08,
            random_state=random_state,
        )
        self.explainer: Any = None
        self.feature_names_: List[str] = []
        self.modality_map_: Dict[str, str] = {}

    def _build_modality_mapping(self):
        """Maps each transformed feature name to its parent modality."""
        self.modality_map_ = {}
        for feat in self.feature_names_:
            if any(feat.startswith(f"num__{a}") for a in ACADEMIC_NUMERIC):
                self.modality_map_[feat] = "academic"
            elif any(feat.startswith(f"num__{b}") for b in BEHAVIORAL_NUMERIC):
                self.modality_map_[feat] = "behavioral"
            elif any(feat.startswith(f"num__{af}") for af in AFFECTIVE_NUMERIC):
                self.modality_map_[feat] = "affective"
            elif "trajectory_label" in feat:
                self.modality_map_[feat] = "behavioral"
            elif "dominant_stress_label" in feat:
                self.modality_map_[feat] = "affective"
            else:
                self.modality_map_[feat] = "behavioral"

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "MultimodalRiskModel":
        """Fits preprocessor, model, and SHAP TreeExplainer."""
        X_trans = self.preprocessor.fit_transform(X[ALL_FEATURE_COLS])
        self.feature_names_ = list(self.preprocessor.get_feature_names_out())
        self._build_modality_mapping()

        self.clf.fit(X_trans, y)
        self.explainer = shap.TreeExplainer(self.clf)
        return self

    def predict_risk(self, X: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Generates contract-compliant multimodal risk assessments for each input row.
        Returns list of dicts with:
          - risk_score: float (0.0 to 1.0)
          - risk_tier: 'low' | 'medium' | 'high' | 'critical'
          - modality_contributions: {affective: float, behavioral: float, academic: float}
          - top_drivers: list of top human-readable factors
        """
        X_trans = self.preprocessor.transform(X[ALL_FEATURE_COLS])
        prob_scores = self.clf.predict_proba(X_trans)[:, 1]

        # Compute SHAP values for explainability
        shap_values = self.explainer.shap_values(X_trans)
        if isinstance(shap_values, list):
            # For binary classification, use positive class SHAP values
            shap_values = shap_values[1]

        results = []
        for i in range(len(X)):
            score = float(np.round(prob_scores[i], 3))
            tier = map_risk_tier(score)

            row_shap = shap_values[i]

            # Aggregate SHAP importances by modality
            abs_shap = np.abs(row_shap)
            mod_sums = {"affective": 0.0, "behavioral": 0.0, "academic": 0.0}

            for f_idx, f_name in enumerate(self.feature_names_):
                mod = self.modality_map_.get(f_name, "behavioral")
                mod_sums[mod] += float(abs_shap[f_idx])

            total_shap = sum(mod_sums.values())
            if total_shap > 1e-6:
                norm_aff = round(mod_sums["affective"] / total_shap, 2)
                norm_beh = round(mod_sums["behavioral"] / total_shap, 2)
                norm_acad = round(1.0 - (norm_aff + norm_beh), 2)  # Guarantee sum to 1.0
            else:
                norm_aff, norm_beh, norm_acad = 0.33, 0.34, 0.33

            modality_contributions = {
                "affective": norm_aff,
                "behavioral": norm_beh,
                "academic": norm_acad,
            }

            # Extract Top Drivers (features with strongest positive contribution to risk)
            # Higher positive SHAP value = pushing student toward risk
            positive_impact_indices = np.argsort(row_shap)[::-1][:4]
            top_drivers = []
            for idx in positive_impact_indices:
                raw_name = self.feature_names_[idx].replace("num__", "").replace("cat__", "")
                val = X[ALL_FEATURE_COLS].iloc[i].get(raw_name.split("_")[0], "")
                clean_name = raw_name.replace("_", " ").title()
                top_drivers.append(clean_name)

            results.append({
                "risk_score": score,
                "risk_tier": tier,
                "modality_contributions": modality_contributions,
                "top_drivers": top_drivers[:4],
            })

        return results

    def save(self, model_dir: str):
        """Saves serialized model and preprocessor to disk."""
        os.makedirs(model_dir, exist_ok=True)
        joblib.dump(self.clf, os.path.join(model_dir, "c3_risk_model.joblib"))
        joblib.dump(self.preprocessor, os.path.join(model_dir, "preprocessor.joblib"))
        with open(os.path.join(model_dir, "feature_names.json"), "w") as f:
            json.dump({"feature_names": self.feature_names_}, f, indent=2)

    @classmethod
    def load(cls, model_dir: str) -> "MultimodalRiskModel":
        """Loads serialized model from disk."""
        instance = cls()
        instance.clf = joblib.load(os.path.join(model_dir, "c3_risk_model.joblib"))
        instance.preprocessor = joblib.load(os.path.join(model_dir, "preprocessor.joblib"))
        with open(os.path.join(model_dir, "feature_names.json"), "r") as f:
            data = json.load(f)
            instance.feature_names_ = data["feature_names"]
        instance._build_modality_mapping()
        instance.explainer = shap.TreeExplainer(instance.clf)
        return instance
