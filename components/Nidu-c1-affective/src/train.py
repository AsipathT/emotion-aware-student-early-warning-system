"""
src/train.py

Training script for DistilRoBERTa multi-label classification (5 academic distress classes).
Features:
- Pure PyTorch training loop compatible with transformers 5.x.
- BCEWithLogitsLoss with positive class weights (pos_weight).
- Evaluates validation macro-F1 at each epoch and saves the best model checkpoint.
- Tunes per-class classification thresholds on val.csv only -> saves to models/thresholds.json.
- Evaluates test_proxy.csv ONCE with best model and tuned thresholds.
- Computes metrics overall and segmented by data source (goemotions_proxy vs emotion4_proxy).
- Supports smoke-testing locally (--max-samples 500 --epochs 1).
"""

import argparse
import json
import logging
import os
from pathlib import Path
import random
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from src.evaluation import (
    DEFAULT_CLASSES,
    compute_multilabel_metrics,
    compute_split_by_source_metrics,
    plot_and_save_confusion_matrices,
    save_evaluation_report,
    tune_thresholds_on_val,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("c1_train")


def set_seed(seed: int = 42) -> None:
    """Sets random seeds for full reproducibility across python, numpy, and torch."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class TextDataset(Dataset):
    """PyTorch Dataset for multi-label text classification."""

    def __init__(
        self,
        texts: List[str],
        labels: Optional[np.ndarray],
        tokenizer: AutoTokenizer,
        max_length: int = 64,
    ):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        text = str(self.texts[idx])
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        item = {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
        }
        if self.labels is not None:
            item["labels"] = torch.tensor(self.labels[idx], dtype=torch.float)
        return item


def predict_probabilities(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: torch.device,
) -> np.ndarray:
    """Generates sigmoid probabilities across all classes for a dataloader."""
    model.eval()
    all_probs = []
    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            probs = torch.sigmoid(logits).cpu().numpy()
            all_probs.append(probs)
    return np.vstack(all_probs)


def train_model(
    component_root: Path,
    pretrained_model_name: str = "distilroberta-base",
    max_length: int = 64,
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    weight_decay: float = 0.01,
    max_samples: Optional[int] = None,
    ablation_source: Optional[str] = None,
    seed: int = 42,
    run_name: Optional[str] = None,
) -> Dict[str, any]:
    """Full training pipeline with validation epoch selection, threshold tuning, and proxy evaluation."""
    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using execution device: {device}")

    data_dir = component_root / "data" / "processed"
    models_dir = component_root / "models"
    reports_metrics_dir = component_root / "reports" / "metrics"
    reports_figures_dir = component_root / "reports" / "figures"

    if run_name:
        run_dir = component_root / "runs" / run_name
        checkpoint_dir = run_dir / "checkpoint-best"
        thresh_file = run_dir / "thresholds.json"
        fig_path = run_dir / "confusion_matrix.png"
        report_json_path = run_dir / f"{run_name}.json"
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = None
        checkpoint_dir = models_dir / ("checkpoint-smoke" if max_samples else "checkpoint-best")
        thresh_file = models_dir / ("thresholds_smoke.json" if max_samples else "thresholds.json")
        fig_name = "confusion_matrix_distilroberta_smoke.png" if max_samples else "confusion_matrix_distilroberta.png"
        fig_path = reports_figures_dir / fig_name
        report_json_name = "distilroberta_smoke.json" if max_samples else "distilroberta_full.json"
        report_json_path = reports_metrics_dir / report_json_name

    models_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    reports_metrics_dir.mkdir(parents=True, exist_ok=True)
    reports_figures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load data
    train_df = pd.read_csv(data_dir / "train.csv")
    val_df = pd.read_csv(data_dir / "val.csv")
    test_df = pd.read_csv(data_dir / "test_proxy.csv")

    if ablation_source:
        logger.info(f"Applying ablation filter: source='{ablation_source}'")
        train_df = train_df[train_df["source"] == ablation_source].copy()

    if max_samples and max_samples > 0:
        logger.info(f"Smoke-test sampling enabled: max_samples={max_samples}")
        train_df = train_df.iloc[:max_samples].copy()
        val_df = val_df.iloc[: max(50, int(max_samples * 0.20))].copy()
        test_df = test_df.iloc[: max(50, int(max_samples * 0.20))].copy()

    logger.info(f"Training set: {len(train_df)} | Validation set: {len(val_df)} | Test proxy: {len(test_df)}")

    # 2. Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(pretrained_model_name)

    # 3. Datasets and DataLoaders
    y_train = train_df[DEFAULT_CLASSES].values.astype(float)
    y_val = val_df[DEFAULT_CLASSES].values.astype(float)
    y_test = test_df[DEFAULT_CLASSES].values.astype(float)

    train_ds = TextDataset(train_df["text"].fillna("").tolist(), y_train, tokenizer, max_length=max_length)
    val_ds = TextDataset(val_df["text"].fillna("").tolist(), y_val, tokenizer, max_length=max_length)
    test_ds = TextDataset(test_df["text"].fillna("").tolist(), y_test, tokenizer, max_length=max_length)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    # 4. Compute positive class weights from training set (clipped at 10.0)
    pos_weights_list = []
    total_samples = len(train_df)
    for cls in DEFAULT_CLASSES:
        pos = train_df[cls].sum()
        neg = total_samples - pos
        w = min(neg / max(1, pos), 10.0)
        pos_weights_list.append(w)

    pos_weight_tensor = torch.tensor(pos_weights_list, dtype=torch.float).to(device)
    logger.info(f"Positive class weights (clipped at 10.0): {pos_weights_list}")

    # 5. Model, Loss, Optimizer
    model = AutoModelForSequenceClassification.from_pretrained(
        pretrained_model_name,
        num_labels=len(DEFAULT_CLASSES),
        problem_type="multi_label_classification",
    ).to(device)

    criterion = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    # 6. Training Loop with best epoch selection
    best_val_macro_f1 = -1.0
    best_thresholds: Dict[str, float] = {cls: 0.50 for cls in DEFAULT_CLASSES}
    best_epoch = 0

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = criterion(outputs.logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            running_loss += loss.item()

        avg_train_loss = running_loss / max(1, len(train_loader))
        logger.info(f"Epoch {epoch}/{epochs} - Average Train Loss: {avg_train_loss:.4f}")

        # Validate
        val_probs = predict_probabilities(model, val_loader, device)
        cur_thresholds = tune_thresholds_on_val(y_val, val_probs, class_names=DEFAULT_CLASSES)
        val_metrics = compute_multilabel_metrics(
            y_val, val_probs, thresholds=cur_thresholds, class_names=DEFAULT_CLASSES
        )
        val_macro_f1 = val_metrics["macro_metrics"]["macro_f1"]
        logger.info(f"Epoch {epoch}/{epochs} - Validation Macro F1: {val_macro_f1:.4f}")

        if val_macro_f1 > best_val_macro_f1:
            best_val_macro_f1 = val_macro_f1
            best_thresholds = cur_thresholds
            best_epoch = epoch
            logger.info(f"--> Best model updated at epoch {epoch} (Val Macro F1 = {val_macro_f1:.4f})")
            # Save checkpoint
            model.save_pretrained(checkpoint_dir)
            tokenizer.save_pretrained(checkpoint_dir)

    # 7. Save optimal thresholds
    with open(thresh_file, "w", encoding="utf-8") as f:
        json.dump(best_thresholds, f, indent=2)
    logger.info(f"Saved tuned thresholds to {thresh_file}")

    # 8. Load best checkpoint and evaluate test_proxy.csv ONCE
    best_model = AutoModelForSequenceClassification.from_pretrained(checkpoint_dir).to(device)
    test_probs = predict_probabilities(best_model, test_loader, device)

    test_overall = compute_multilabel_metrics(
        y_test, test_probs, thresholds=best_thresholds, class_names=DEFAULT_CLASSES
    )
    test_by_source = compute_split_by_source_metrics(
        test_df, test_probs, thresholds=best_thresholds, class_names=DEFAULT_CLASSES
    )

    # 9. Plot and save confusion matrix
    plot_and_save_confusion_matrices(
        y_test,
        test_probs,
        thresholds=best_thresholds,
        output_png=fig_path,
        model_name=f"DistilRoBERTa (Best Epoch {best_epoch})",
        class_names=DEFAULT_CLASSES,
    )

    result_report = {
        "model_name": pretrained_model_name,
        "evaluation_type": "proxy test",
        "best_epoch": best_epoch,
        "total_epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "max_length": max_length,
        "smoke_test": bool(max_samples),
        "ablation_training_source": ablation_source or "all_sources",
        "sample_counts": {
            "train": len(train_df),
            "val": len(val_df),
            "test_proxy": len(test_df),
        },
        "pos_weights_applied": {cls: round(float(w), 4) for cls, w in zip(DEFAULT_CLASSES, pos_weights_list)},
        "tuned_val_thresholds": best_thresholds,
        "overall_test_proxy_metrics": test_overall,
        "metrics_by_source": test_by_source,
    }
    if run_name:
        result_report["run_name"] = run_name

    save_evaluation_report(result_report, report_json_path)
    if run_name:
        save_evaluation_report(result_report, reports_metrics_dir / f"{run_name}.json")

    return result_report


def main():
    parser = argparse.ArgumentParser(description="Train DistilRoBERTa for C1 Affective State Detection")
    parser.add_argument("--max-samples", type=int, default=None, help="Smoke test sample count")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--seed", type=int, default=42, help="Seed")
    parser.add_argument("--ablation", type=str, default=None, help="Train only on specific source (e.g. goemotions_proxy)")
    parser.add_argument("--run-name", type=str, default=None, help="Optional run identifier writing outputs to runs/<run-name>/")
    args = parser.parse_args()

    component_root = Path(__file__).resolve().parents[1]
    res = train_model(
        component_root=component_root,
        max_length=64,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        max_samples=args.max_samples,
        ablation_source=args.ablation,
        seed=args.seed,
        run_name=args.run_name,
    )

    if args.max_samples:
        mode_label = "SMOKE TEST"
    elif args.ablation:
        mode_label = f"ABLATION ({args.ablation})"
    else:
        mode_label = "FULL"

    if args.run_name:
        mode_label += f" | RUN: {args.run_name}"

    print("\n" + "=" * 60)
    print(f"DISTILROBERTA TRAINING COMPLETE ({mode_label})")
    print("=" * 60)
    print(f"Best Epoch:      {res['best_epoch']} / {res['total_epochs']}")
    print(f"Macro F1:        {res['overall_test_proxy_metrics']['macro_metrics']['macro_f1']:.4f}")
    print(f"Macro Precision: {res['overall_test_proxy_metrics']['macro_metrics']['macro_precision']:.4f}")
    print(f"Macro Recall:    {res['overall_test_proxy_metrics']['macro_metrics']['macro_recall']:.4f}")
    print(f"Macro ROC-AUC:   {res['overall_test_proxy_metrics']['macro_metrics']['macro_roc_auc']:.4f}")
    print("\nTuned Thresholds on Val:")
    for cls, t in res["tuned_val_thresholds"].items():
        print(f"  {cls:24s}: {t:.2f}")
    print("\nPer-Class Test Metrics:")
    for cls, m in res["overall_test_proxy_metrics"]["per_class_metrics"].items():
        print(f"  {cls:24s} | P: {m['precision']:.4f} | R: {m['recall']:.4f} | F1: {m['f1']:.4f} | AUC: {m['roc_auc']:.4f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
