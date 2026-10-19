"""
service/plotting.py

Visualization utility for Component 2 behavioral trajectories.
Renders student weekly clickstream trajectories alongside predicted trajectory labels
and contributing indicators into a multi-subplot grid PNG at 150 DPI.
"""

from pathlib import Path
from typing import Any, List, Union

import matplotlib
matplotlib.use("Agg")
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt

from service.schemas import BehaviorRecord, TrajectoryRecord

# Line colors by trajectory label (stable grey-blue, improving green, declining red, volatile orange)
LABEL_COLORS = {
    "stable": "#475569",    # grey-blue (slate)
    "improving": "#16a34a", # green
    "declining": "#dc2626", # red
    "volatile": "#ea580c",  # orange
}


def plot_trajectories(
    behavior_records: List[BehaviorRecord],
    trajectories: List[TrajectoryRecord],
    out_path: Union[str, Path],
    title: str,
) -> None:
    """
    Plot weekly clicks for each classified student in a 3-column grid.

    Parameters:
      behavior_records: Weekly student interaction records.
      trajectories: Classified engagement trajectory records.
      out_path: Destination path for the saved PNG file.
      title: Shared figure title.
    """
    sorted_trajectories = sorted(
        trajectories,
        key=lambda t: (str(getattr(t, "pid", "")), str(getattr(t, "course_id", "")))
    )

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    n = len(sorted_trajectories)
    if n == 0:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "No classified trajectories to display", ha="center", va="center")
        ax.axis("off")
        fig.suptitle(title, fontsize=12)
        fig.savefig(out_file, dpi=150)
        plt.close(fig)
        return

    # Build click lookup maps: (pid, course_id) -> {week_index: clicks}
    clicks_by_key: dict[tuple[str, str], dict[int, int]] = {}
    clicks_by_pid: dict[str, dict[int, int]] = {}
    for r in behavior_records:
        pid = str(getattr(r, "pid", "") if not isinstance(r, dict) else r.get("pid", ""))
        cid = str(getattr(r, "course_id", "") if not isinstance(r, dict) else r.get("course_id", ""))
        w = int(getattr(r, "week_index", 0) if not isinstance(r, dict) else r.get("week_index", 0))
        c = int(getattr(r, "clicks", 0) if not isinstance(r, dict) else r.get("clicks", 0))

        key = (pid, cid)
        if key not in clicks_by_key:
            clicks_by_key[key] = {}
        clicks_by_key[key][w] = c

        if pid not in clicks_by_pid:
            clicks_by_pid[pid] = {}
        clicks_by_pid[pid][w] = c

    ncols = 3
    nrows = (n + ncols - 1) // ncols

    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=(12, max(3.5, 3.2 * nrows)),
        squeeze=False,
    )

    for idx, traj in enumerate(sorted_trajectories):
        row = idx // ncols
        col = idx % ncols
        ax = axes[row, col]

        pid_raw = str(getattr(traj, "pid", ""))
        pid_suffix = pid_raw[-4:] if len(pid_raw) >= 4 else pid_raw
        label_raw = str(getattr(traj, "trajectory_label", "")).lower()
        conf_raw = float(getattr(traj, "confidence", 0.0))
        color = LABEL_COLORS.get(label_raw, "#475569")

        course_id = str(getattr(traj, "course_id", ""))
        target_w = int(getattr(traj, "week_index", 0))

        hist = clicks_by_key.get((pid_raw, course_id)) or clicks_by_pid.get(pid_raw, {})
        x = list(range(0, target_w + 1))
        y = [hist.get(w, 0) for w in x]

        ax.plot(
            x,
            y,
            marker="o",
            markersize=4,
            color=color,
            linewidth=1.8,
            label=label_raw,
        )

        sub_title = f"{pid_suffix} | {label_raw} ({conf_raw:.2f})"
        ax.set_title(sub_title, fontsize=9.5, fontweight="bold", pad=14)

        indicators = getattr(traj, "contributing_indicators", []) or []
        if isinstance(indicators, (list, tuple)):
            ind_str = ",".join(str(item) for item in indicators)
        else:
            ind_str = str(indicators)

        if ind_str:
            ax.text(
                0.5,
                1.02,
                ind_str,
                transform=ax.transAxes,
                ha="center",
                va="bottom",
                fontsize=7.5,
                color="#475569",
            )

        max_y = max(y) if y else 0
        if max_y == 0:
            ax.set_ylim(-0.5, 5.0)
        else:
            ax.set_ylim(bottom=0, top=max_y * 1.18 + 1.0)

        if target_w > 0:
            ax.set_xticks(range(0, target_w + 1))

        ax.set_xlabel("Week", fontsize=8)
        ax.set_ylabel("Clicks", fontsize=8)
        ax.tick_params(axis="both", labelsize=8)
        ax.grid(True, linestyle="--", alpha=0.35)

    # Hide unused subplot axes in the grid
    for idx in range(n, nrows * ncols):
        row = idx // ncols
        col = idx % ncols
        axes[row, col].set_visible(False)

    # Shared suptitle
    fig.suptitle(title, fontsize=12.5, fontweight="bold", y=0.985)

    # Shared 4-color legend
    legend_elements = [
        Line2D([0], [0], color=LABEL_COLORS["stable"], marker="o", markersize=4, lw=1.8, label="Stable (grey-blue)"),
        Line2D([0], [0], color=LABEL_COLORS["improving"], marker="o", markersize=4, lw=1.8, label="Improving (green)"),
        Line2D([0], [0], color=LABEL_COLORS["declining"], marker="o", markersize=4, lw=1.8, label="Declining (red)"),
        Line2D([0], [0], color=LABEL_COLORS["volatile"], marker="o", markersize=4, lw=1.8, label="Volatile (orange)"),
    ]
    fig.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.95),
        ncol=4,
        frameon=True,
        fontsize=8.5,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(out_file, dpi=150)
    plt.close(fig)
