"""Retrain the intervention model and save it to backend/model/c4_intervention_model.joblib.

Usage (from the backend folder):
    python train_model.py                      # uses model/C4_ML_Training_Dataset_500_IT23_v2.xlsx
    python train_model.py path/to/data.xlsx    # or a .csv with the same columns
"""
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score

from app import config
from app.model_service import TARGET, build_pipeline, prepare_training_features


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else config.TRAINING_DATA_PATH
    df = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path, sheet_name=0)
    df = df.dropna(subset=[TARGET]).drop_duplicates()
    X, y = prepare_training_features(df), df[TARGET]

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(build_pipeline(), X, y, cv=cv, scoring="accuracy")
    print(f"Rows: {len(df)}   5-fold CV accuracy: {scores.mean():.3f} ± {scores.std():.3f}")

    pipeline = build_pipeline().fit(X, y)
    config.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, config.MODEL_PATH)
    print("Saved", config.MODEL_PATH)


if __name__ == "__main__":
    main()
