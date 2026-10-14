"""Loads the trained intervention model and ranks interventions for one student.

The pipeline is the same as in C4_Suitable_Intervention_Model.ipynb:
one-hot encode C1_Condition, C2_Trajectory, Risk_Tier and C3_Dominant, then Gradient Boosting.
A model exported from the notebook (c4_intervention_model.joblib) can be dropped into backend/model/.
"""
import logging
import warnings
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

log = logging.getLogger("c4")

TARGET = "Suitable_Intervention"
FEATURES = ["C1_Condition", "C2_Trajectory", "Risk_Tier", "C3_Dominant"]

MODEL_NAMES = {
    "GradientBoostingClassifier": "Gradient Boosting",
    "RandomForestClassifier": "Random Forest",
    "LogisticRegression": "Logistic Regression",
}


# ---------- training (same steps as the notebook) ----------

def strongest_c3(text):
    """'Affective: 0.15, Behavioural: 0.39, Academic: 0.46' -> 'Academic'"""
    scores = {}
    for part in str(text).split(","):
        name, value = part.split(":")
        scores[name.strip().title()] = float(value)
    return max(scores, key=scores.get)


def prepare_training_features(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    for col in ["C1_Condition", "C2_Trajectory", "Risk_Tier"]:
        data[col] = data[col].astype(str).str.strip().str.title()
    data["C3_Dominant"] = data["C3_Vector"].apply(strongest_c3)
    return data[FEATURES]


def build_pipeline() -> Pipeline:
    encoder = ColumnTransformer([("onehot", OneHotEncoder(handle_unknown="ignore"), FEATURES)])
    model = GradientBoostingClassifier(learning_rate=0.05, max_depth=2, random_state=42)
    return Pipeline([("encode", encoder), ("model", model)])


def train(training_data_path: Path) -> Pipeline:
    path = str(training_data_path)
    df = pd.read_csv(path) if path.lower().endswith(".csv") else pd.read_excel(path, sheet_name=0)
    df = df.dropna(subset=[TARGET]).drop_duplicates()
    return build_pipeline().fit(prepare_training_features(df), df[TARGET])


# ---------- inference ----------

class InterventionModel:
    def __init__(self, model_path: Path, training_data_path: Path):
        self.pipeline = self._load_or_train(Path(model_path), Path(training_data_path))
        estimator = self.pipeline.named_steps["model"]
        self.name = MODEL_NAMES.get(type(estimator).__name__, type(estimator).__name__)
        self.classes = list(self.pipeline.classes_)

    @staticmethod
    def _load_or_train(model_path: Path, training_data_path: Path) -> Pipeline:
        if model_path.exists():
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", InconsistentVersionWarning)
                    return joblib.load(model_path)
            except InconsistentVersionWarning as exc:
                log.warning("Saved model was made with another scikit-learn version (%s); retraining.", exc)
            except Exception as exc:  # corrupt or incompatible file
                log.warning("Could not load %s (%s); retraining.", model_path, exc)
        if not training_data_path.exists():
            raise FileNotFoundError(
                f"No usable model at {model_path} and no training data at {training_data_path}.")
        log.info("Training model from %s", training_data_path)
        pipeline = train(training_data_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, model_path)
        return pipeline

    def rank(self, c1_condition: str, c2_trajectory: str, risk_tier: str, c3_dominant: str):
        """All interventions with their suitability score (model probability), best first."""
        row = pd.DataFrame([{
            "C1_Condition": c1_condition,
            "C2_Trajectory": c2_trajectory,
            "Risk_Tier": risk_tier,
            "C3_Dominant": c3_dominant,
        }])[FEATURES]
        proba = self.pipeline.predict_proba(row)[0]
        ranked = sorted(zip(self.classes, proba), key=lambda item: item[1], reverse=True)
        return [{"intervention": name, "suitability": round(float(p), 4)} for name, p in ranked]
