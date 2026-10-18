"""
scripts/make_figures.py

Generates evaluation and analysis figures for Component 2:
  - fig1_model_comparison.png: Bar chart test macro-F1 of majority, b2_rule, b1_static, c2_model
  - fig2_confusion_c2_test.png: Confusion matrix heatmap of c2_model on test (row-normalized %)
  - fig3_label_distribution.png: Bar chart of label_share_nondormant
  - fig4_ablation.png: Bar chart of macro-F1 across feature ablations (y-axis: 0.45-0.52)
Saves figures to reports/figures/ at 150 DPI using matplotlib Agg backend.
"""

import json
from pathlib import Path
import sys

# Ensure components/c2-behavioral root is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
COMPONENT_ROOT = SCRIPT_DIR.parent
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    reports_dir = COMPONENT_ROOT / "reports"
    metrics_dir = reports_dir / "metrics"
    figures_dir = reports_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    written_files = []

    # ──────────────────────────────────────────────────────────────────────────
    # Fig 1: Model Comparison (Test Macro-F1)
    # ──────────────────────────────────────────────────────────────────────────
    model_eval_path = metrics_dir / "model_eval.json"
    with open(model_eval_path, "r", encoding="utf-8") as f:
        model_eval = json.load(f)

    results = model_eval["results"]
    m_keys = ["majority", "b2_rule", "b1_static", "c2_model"]
    m_labels = ["Majority", "B2 (Rule)", "B1 (Static)", "C2 Model"]
    f1_scores = [results[m]["test"]["macro_f1"] for m in m_keys]

    fig1, ax1 = plt.subplots(figsize=(8, 5))
    bars1 = ax1.bar(
        m_labels,
        f1_scores,
        color=["#94a3b8", "#64748b", "#3b82f6", "#1d4ed8"],
        width=0.55,
        edgecolor="#1e293b",
        linewidth=0.8,
    )
    ax1.set_ylabel("Macro-F1 Score", fontsize=11)
    ax1.set_xlabel("Model / Baseline", fontsize=11)
    ax1.set_title("Model Comparison on Test Split (Macro-F1)", fontsize=13, fontweight="bold", pad=12)
    ax1.set_ylim(0, max(f1_scores) * 1.18)
    ax1.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars1:
        yval = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + 0.01,
            f"{yval:.4f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    fig1.tight_layout()
    fig1_path = figures_dir / "fig1_model_comparison.png"
    fig1.savefig(fig1_path, dpi=150)
    plt.close(fig1)
    written_files.append(fig1_path)

    # ──────────────────────────────────────────────────────────────────────────
    # Fig 2: Confusion Matrix Heatmap (C2 Model on Test Split)
    # ──────────────────────────────────────────────────────────────────────────
    cm_raw = np.array(results["c2_model"]["test"]["confusion_matrix"], dtype=float)
    # Row-normalize to percentages
    row_sums = cm_raw.sum(axis=1, keepdims=True)
    cm_pct = np.divide(cm_raw, row_sums, out=np.zeros_like(cm_raw), where=row_sums != 0) * 100.0

    class_names = ["declining", "improving", "stable", "volatile"]
    fig2, ax2 = plt.subplots(figsize=(7, 6))
    im2 = ax2.imshow(cm_pct, cmap="Blues", vmin=0, vmax=100, interpolation="nearest")
    cbar2 = fig2.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
    cbar2.set_label("Row Percentage (%)", fontsize=10)

    ax2.set_xticks(range(len(class_names)))
    ax2.set_yticks(range(len(class_names)))
    ax2.set_xticklabels(class_names, fontsize=10)
    ax2.set_yticklabels(class_names, fontsize=10)
    ax2.set_xlabel("Predicted Label", fontsize=11, labelpad=8)
    ax2.set_ylabel("True Label", fontsize=11, labelpad=8)
    ax2.set_title("C2 Model Confusion Matrix: Test Split (Row-Normalized %)", fontsize=12, fontweight="bold", pad=12)

    for i in range(len(class_names)):
        for j in range(len(class_names)):
            pct_val = cm_pct[i, j]
            cnt_val = int(cm_raw[i, j])
            text_color = "white" if pct_val > 50 else "black"
            ax2.text(
                j,
                i,
                f"{pct_val:.1f}%\n({cnt_val:,})",
                ha="center",
                va="center",
                color=text_color,
                fontsize=9,
            )

    fig2.tight_layout()
    fig2_path = figures_dir / "fig2_confusion_c2_test.png"
    fig2.savefig(fig2_path, dpi=150)
    plt.close(fig2)
    written_files.append(fig2_path)

    # ──────────────────────────────────────────────────────────────────────────
    # Fig 3: Label Distribution (Non-dormant Windows)
    # ──────────────────────────────────────────────────────────────────────────
    label_report_path = metrics_dir / "label_report.json"
    with open(label_report_path, "r", encoding="utf-8") as f:
        label_report = json.load(f)

    share_dict = label_report["label_share_nondormant"]
    labels_order = ["declining", "improving", "stable", "volatile"]
    display_labels = ["Declining", "Improving", "Stable", "Volatile"]
    shares = [share_dict[k] for k in labels_order]
    shares_pct = [s * 100.0 for s in shares]

    fig3, ax3 = plt.subplots(figsize=(8, 5))
    bars3 = ax3.bar(
        display_labels,
        shares_pct,
        color=["#ef4444", "#22c55e", "#3b82f6", "#f59e0b"],
        width=0.55,
        edgecolor="#1e293b",
        linewidth=0.8,
    )
    ax3.set_ylabel("Share of Non-dormant Windows (%)", fontsize=11)
    ax3.set_xlabel("Trajectory Label", fontsize=11)
    ax3.set_title("Label Distribution (Non-dormant Windows)", fontsize=13, fontweight="bold", pad=12)
    ax3.set_ylim(0, max(shares_pct) * 1.2)
    ax3.grid(axis="y", linestyle="--", alpha=0.5)

    for bar, s in zip(bars3, shares):
        yval = bar.get_height()
        ax3.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + 0.8,
            f"{yval:.1f}%\n({s:.3f})",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    fig3.tight_layout()
    fig3_path = figures_dir / "fig3_label_distribution.png"
    fig3.savefig(fig3_path, dpi=150)
    plt.close(fig3)
    written_files.append(fig3_path)

    # ──────────────────────────────────────────────────────────────────────────
    # Fig 4: Feature Ablation Study
    # ──────────────────────────────────────────────────────────────────────────
    ablation_path = metrics_dir / "ablation_evidence.json"
    with open(ablation_path, "r", encoding="utf-8") as f:
        ablation_data = json.load(f)

    ablation = ablation_data["ablation"]
    abl_keys = ["clicks", "clicks_activity", "full"]
    abl_labels = ["Clicks Only", "Clicks + Activity", "Full Features"]
    abl_f1 = [ablation[k]["macro_f1"] for k in abl_keys]

    fig4, ax4 = plt.subplots(figsize=(8, 5))
    bars4 = ax4.bar(
        abl_labels,
        abl_f1,
        color=["#60a5fa", "#3b82f6", "#1d4ed8"],
        width=0.5,
        edgecolor="#1e293b",
        linewidth=0.8,
    )
    ax4.set_ylabel("Macro-F1 Score", fontsize=11)
    ax4.set_xlabel("Feature Set", fontsize=11)
    ax4.set_title("Feature Ablation Study (Test Macro-F1)", fontsize=13, fontweight="bold", pad=12)
    ax4.set_ylim(0.45, 0.52)
    ax4.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars4:
        yval = bar.get_height()
        ax4.text(
            bar.get_x() + bar.get_width() / 2.0,
            yval + 0.001,
            f"{yval:.4f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    ax4.text(
        0.5,
        0.91,
        "Note: differences are small",
        transform=ax4.transAxes,
        ha="center",
        va="top",
        fontsize=10,
        fontstyle="italic",
        bbox=dict(boxstyle="round,pad=0.3", fc="#f8fafc", ec="#cbd5e1", alpha=0.9),
    )

    fig4.tight_layout()
    fig4_path = figures_dir / "fig4_ablation.png"
    fig4.savefig(fig4_path, dpi=150)
    plt.close(fig4)
    written_files.append(fig4_path)

    # ──────────────────────────────────────────────────────────────────────────
    # Print List of Written Files
    # ──────────────────────────────────────────────────────────────────────────
    print("Generated figures:")
    for path in written_files:
        print(f"  {path.relative_to(COMPONENT_ROOT)}")


if __name__ == "__main__":
    main()
