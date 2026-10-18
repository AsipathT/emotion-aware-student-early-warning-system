"""
components/Thilina-c3-risk-prediction/src/train.py

Training script for Component 3 Multimodal Risk Model.
Trains on data/multimodal_risk_training_data.csv and saves model to models/.
"""

import os
import sys

# Ensure component root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, f1_score

from src.model import MultimodalRiskModel, ALL_FEATURE_COLS

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "multimodal_risk_training_data.csv")
    model_dir = os.path.join(base_dir, "models")

    if not os.path.exists(data_path):
        print(f"[!] Dataset not found at {data_path}. Running generator first...")
        from src.generate_multimodal_dataset import generate_multimodal_data
        df = generate_multimodal_data(num_students=400, num_weeks=12)
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        df.to_csv(data_path, index=False)
    else:
        df = pd.read_csv(data_path)

    print(f"[*] Loaded dataset with {len(df)} records across {df['pid'].nunique()} students.")

    # Target: Predict actual_dropout (1 = high risk/dropout, 0 = safe)
    # Alternatively high risk tier (high or critical)
    y = df["actual_dropout"].values
    X = df[ALL_FEATURE_COLS]

    # Student-aware train/test split (split by student PID to prevent data leakage across weeks)
    unique_pids = df["pid"].unique()
    train_pids, test_pids = train_test_split(unique_pids, test_size=0.20, random_state=42)

    train_mask = df["pid"].isin(train_pids)
    test_mask = df["pid"].isin(test_pids)

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]

    print(f"[*] Training on {len(X_train)} weekly samples ({len(train_pids)} students)...")
    print(f"[*] Testing on {len(X_test)} weekly samples ({len(test_pids)} students)...")

    model = MultimodalRiskModel(n_estimators=120, max_depth=5, random_state=42)
    model.fit(X_train, y_train)

    # Predictions & Evaluation
    X_test_trans = model.preprocessor.transform(X_test)
    y_pred_proba = model.clf.predict_proba(X_test_trans)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_test, y_pred_proba)
    f1 = f1_score(y_test, y_pred)

    print("\n" + "=" * 55)
    print("  MODEL EVALUATION METRICS (C3 MULTIMODAL RISK)")
    print("=" * 55)
    print(f"  ROC-AUC Score : {auc:.4f}")
    print(f"  F1 Score      : {f1:.4f}")
    print("-" * 55)
    print(classification_report(y_test, y_pred, target_names=["Safe (0)", "At Risk / Dropout (1)"]))
    print("=" * 55)

    # Save model artifacts
    model.save(model_dir)
    print(f"\n[OK] Trained model artifacts successfully saved to: {model_dir}")

    # Test an inference sample
    sample_df = X_test.iloc[:2]
    sample_predictions = model.predict_risk(sample_df)
    print("\nSample Explainable Risk Output (Contract-Compliant):")
    for i, pred in enumerate(sample_predictions):
        print(f"  Student {i+1}:")
        print(f"    Risk Score : {pred['risk_score']} ({pred['risk_tier'].upper()})")
        print(f"    Modality Contributions : {pred['modality_contributions']}")
        print(f"    Top Drivers : {pred['top_drivers']}")

if __name__ == "__main__":
    main()
