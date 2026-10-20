"""
components/Thilina-c3-risk-prediction/src/model.py

C3: Multimodal Risk Prediction Model & Explainability Pipeline.
Trains an ensemble model combining Academic, Behavioral, and Affective modalities.
Calculates:
  - risk_score (0.0 to 1.0)
  - risk_tier ('low', 'medium', 'high', 'critical')
  - modality_contributions ({affective: float, behavioral: float, academic: float}) summing to 1.0
  - top_drivers (SHAP-ranked human-readable risk drivers)
  - top_modality ('affective' | 'behavioural' | 'academic')
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
import shap

# Feature grouping by modality (matching contracts/v1 field names)
ACADEMIC_NUMERIC = [
    "attendance_pct",
    "ca_marks",
    "midterm_mark",
    "quiz_score",
    "submission_delay_hours",
]

BEHAVIORAL_NUMERIC = [
    "login_count",
    "session_minutes",
    "clicks",
    "video_play_count",
    "video_pause_count",
    "video_rewind_count",
    "video_skip_count",
    "video_completion_pct",
    "submissions_count",
    "avg_submission_delay_hours",
]

AFFECTIVE_NUMERIC = [
    "message_count",
    "exam_anxiety",
    "conceptual_confusion",
    "academic_helplessness",
    "course_frustration",
    "motivation_erosion",
    "confidence",
]

CATEGORICAL_FEATURES = [
    "trajectory_label",
    "stress_label",
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
    def __init__(self, n_estimators: int = 150, max_depth: int = 5, learning_rate: float = 0.08, random_state: int = 42):
        self.random_state = random_state
        numeric_cols = ACADEMIC_NUMERIC + BEHAVIORAL_NUMERIC + AFFECTIVE_NUMERIC

        num_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])

        cat_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ])

        self.preprocessor = ColumnTransformer(
            transformers=[
                ("num", num_pipeline, numeric_cols),
                ("cat", cat_pipeline, CATEGORICAL_FEATURES),
            ]
        )
        self.clf = GradientBoostingClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            random_state=random_state,
        )
        self.explainer: Any = None
        self.feature_names_: List[str] = []
        self.modality_map_: Dict[str, str] = {}

    def _build_modality_mapping(self):
        """Maps each transformed feature name to its parent modality."""
        self.modality_map_ = {}
        for feat in self.feature_names_:
            clean = feat.replace("num__", "").replace("cat__", "")
            if any(clean.startswith(a) for a in ACADEMIC_NUMERIC):
                self.modality_map_[feat] = "academic"
            elif any(clean.startswith(b) for b in BEHAVIORAL_NUMERIC):
                self.modality_map_[feat] = "behavioural"
            elif any(clean.startswith(af) for af in AFFECTIVE_NUMERIC):
                self.modality_map_[feat] = "affective"
            elif clean.startswith("trajectory_label"):
                self.modality_map_[feat] = "behavioural"
            elif clean.startswith("stress_label"):
                self.modality_map_[feat] = "affective"
            else:
                self.modality_map_[feat] = "behavioural"

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
          - top_modality: 'affective' | 'behavioural' | 'academic'
        """
        X_trans = self.preprocessor.transform(X[ALL_FEATURE_COLS])
        prob_scores = self.clf.predict_proba(X_trans)[:, 1]

        # Compute SHAP values for explainability
        shap_values = self.explainer.shap_values(X_trans)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        results = []
        for i in range(len(X)):
            score = float(np.round(prob_scores[i], 3))
            tier = map_risk_tier(score)

            row_shap = shap_values[i]

            # Aggregate SHAP importances by modality
            abs_shap = np.abs(row_shap)
            mod_sums = {"affective": 0.0, "behavioural": 0.0, "academic": 0.0}

            for f_idx, f_name in enumerate(self.feature_names_):
                mod = self.modality_map_.get(f_name, "behavioural")
                mod_sums[mod] += float(abs_shap[f_idx])

            total_shap = sum(mod_sums.values())
            if total_shap > 1e-6:
                norm_aff = round(mod_sums["affective"] / total_shap, 2)
                norm_beh = round(mod_sums["behavioural"] / total_shap, 2)
                norm_acad = round(1.0 - (norm_aff + norm_beh), 2)
            else:
                norm_aff, norm_beh, norm_acad = 0.33, 0.34, 0.33

            modality_contributions = {
                "affective": norm_aff,
                "behavioral": norm_beh,
                "academic": norm_acad,
            }

            top_mod = max(mod_sums, key=mod_sums.get)

            # Extract Top Drivers (features with strongest positive contribution pushing towards risk)
            positive_impact_indices = np.argsort(row_shap)[::-1][:4]
            top_drivers = []
            for idx in positive_impact_indices:
                raw_name = self.feature_names_[idx].replace("num__", "").replace("cat__", "")
                clean_name = raw_name.replace("_", " ").title()
                top_drivers.append(clean_name)

            results.append({
                "risk_score": score,
                "risk_tier": tier,
                "modality_contributions": modality_contributions,
                "top_drivers": top_drivers[:4],
                "top_modality": top_mod,
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


# ── Sequential Deep Learning Architecture: BiLSTM ──────────────────────────────

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import TensorDataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


if HAS_TORCH:
    class BiLSTMNet(nn.Module):
        """
        Bidirectional LSTM Neural Network for Longitudinal Student Dropout Risk.
        Captures forward and backward temporal telemetry trends across academic weeks.
        """
        def __init__(self, input_dim: int, hidden_dim: int = 48, num_layers: int = 2, dropout: float = 0.25):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.num_layers = num_layers
            self.lstm = nn.LSTM(
                input_size=input_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                bidirectional=True,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.classifier = nn.Sequential(
                nn.Linear(hidden_dim * 2, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, 1),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # x shape: (batch_size, window_size, input_dim)
            lstm_out, _ = self.lstm(x)
            last_timestep = lstm_out[:, -1, :]  # (batch_size, 2 * hidden_dim)
            logits = self.classifier(last_timestep).squeeze(-1)
            return logits


    class BiLSTMRiskModel:
        """
        Sequence-based Risk Prediction Model wrapping BiLSTMNet and Scikit-Learn Preprocessing.
        Takes temporal student history windows and produces calibrated dropout probabilities.
        """
        def __init__(
            self,
            hidden_dim: int = 48,
            num_layers: int = 2,
            dropout: float = 0.25,
            window_size: int = 5,
            lr: float = 0.0015,
            epochs: int = 12,
            batch_size: int = 128,
            random_state: int = 42,
        ):
            self.hidden_dim = hidden_dim
            self.num_layers = num_layers
            self.dropout = dropout
            self.window_size = window_size
            self.lr = lr
            self.epochs = epochs
            self.batch_size = batch_size
            self.random_state = random_state

            self.preprocessor = None
            self.net = None
            self.input_dim = None

        def build_temporal_windows(self, df: pd.DataFrame) -> np.ndarray:
            """Constructs (N, window_size, feature_dim) temporal tensor per student."""
            X_trans = self.preprocessor.transform(df[ALL_FEATURE_COLS])
            num_features = X_trans.shape[1]

            df_indexed = df.copy()
            df_indexed["_row_idx"] = np.arange(len(df))

            sequences = []
            for _, group in df_indexed.groupby("pid"):
                sorted_group = group.sort_values("week_index")
                row_indices = sorted_group["_row_idx"].values
                student_feats = X_trans[row_indices]

                for step in range(len(student_feats)):
                    start_idx = max(0, step - self.window_size + 1)
                    window = student_feats[start_idx : step + 1]
                    if len(window) < self.window_size:
                        pad_len = self.window_size - len(window)
                        pad = np.zeros((pad_len, num_features))
                        window = np.vstack([pad, window])
                    sequences.append((row_indices[step], window))

            sequences.sort(key=lambda item: item[0])
            return np.array([item[1] for item in sequences], dtype=np.float32)

        def fit(self, df: pd.DataFrame, y: np.ndarray, preprocessor=None) -> "BiLSTMRiskModel":
            """Fits BiLSTM on student sequential window representations."""
            torch.manual_seed(self.random_state)
            np.random.seed(self.random_state)

            if preprocessor is not None:
                self.preprocessor = preprocessor
            else:
                temp_model = MultimodalRiskModel()
                self.preprocessor = temp_model.preprocessor
                self.preprocessor.fit(df[ALL_FEATURE_COLS])

            X_seq = self.build_temporal_windows(df)
            self.input_dim = X_seq.shape[2]

            self.net = BiLSTMNet(
                input_dim=self.input_dim,
                hidden_dim=self.hidden_dim,
                num_layers=self.num_layers,
                dropout=self.dropout,
            )

            # Handle class imbalance
            pos_weight_val = float((len(y) - y.sum()) / max(1.0, y.sum()))
            criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight_val], dtype=torch.float32))
            optimizer = torch.optim.AdamW(self.net.parameters(), lr=self.lr, weight_decay=1e-4)

            dataset = TensorDataset(torch.from_numpy(X_seq), torch.from_numpy(y.astype(np.float32)))
            loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

            self.net.train()
            for _ in range(self.epochs):
                for bx, by in loader:
                    optimizer.zero_grad()
                    logits = self.net(bx)
                    loss = criterion(logits, by)
                    loss.backward()
                    optimizer.step()

            return self

        def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
            """Predicts dropout risk probabilities for sequential windows."""
            self.net.eval()
            X_seq = self.build_temporal_windows(df)
            with torch.no_grad():
                logits = self.net(torch.from_numpy(X_seq))
                probs = torch.sigmoid(logits).cpu().numpy()
            return probs

        def save(self, model_dir: str):
            """Saves PyTorch weights and configuration to disk."""
            os.makedirs(model_dir, exist_ok=True)
            model_path = os.path.join(model_dir, "bilstm_risk_model.pt")
            torch.save({
                "state_dict": self.net.state_dict(),
                "input_dim": self.input_dim,
                "hidden_dim": self.hidden_dim,
                "num_layers": self.num_layers,
                "window_size": self.window_size,
            }, model_path)

        @classmethod
        def load(cls, model_dir: str, preprocessor) -> "BiLSTMRiskModel":
            """Loads serialized BiLSTM model from disk."""
            model_path = os.path.join(model_dir, "bilstm_risk_model.pt")
            checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
            instance = cls(
                hidden_dim=checkpoint["hidden_dim"],
                num_layers=checkpoint["num_layers"],
                window_size=checkpoint["window_size"],
            )
            instance.preprocessor = preprocessor
            instance.input_dim = checkpoint["input_dim"]
            instance.net = BiLSTMNet(
                input_dim=instance.input_dim,
                hidden_dim=instance.hidden_dim,
                num_layers=instance.num_layers,
            )
            instance.net.load_state_dict(checkpoint["state_dict"])
            instance.net.eval()
            return instance

