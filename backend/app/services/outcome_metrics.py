"""
backend/app/services/outcome_metrics.py

Feature 35: Intervention Outcome Evaluation & Evidence Computation (Component 4 FR8/FR9).
Provides pure functions to compute objective before/after deltas, weeks-to-improvement metrics,
and PII-free observed change summaries for the adaptive feedback loop.
"""

from typing import Any, Dict, List, Literal, Optional

# Tier ranking: low < medium < high < critical
TIER_ORDER: Dict[str, int] = {
    "unknown": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

# Trajectory ranking: declining < volatile < stable < improving
TRAJECTORY_ORDER: Dict[str, int] = {
    "unknown": 0,
    "declining": 1,
    "volatile": 2,
    "stable": 3,
    "improving": 4,
}


def compute_outcome_delta(
    baseline: Dict[str, Any],
    followup: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Computes comparative delta metrics between the baseline snapshot (captured at review)
    and the latest follow-up analytics.

    Evaluation Rules:
      1. Tier Transition:
         - A decrease in risk tier (e.g., 'high' -> 'medium') indicates an improvement.
         - An increase in risk tier indicates worsening.
      2. Trajectory Transition:
         - If tier remains unchanged, an improvement in trajectory ('declining'/'volatile' -> 'stable'/'improving')
           indicates an improvement.
      3. Risk Score Delta:
         - If tier and trajectory remain unchanged, risk_score delta is evaluated:
           delta < -0.01 -> improved; delta > +0.01 -> worsened; otherwise -> no_change.

    Returns:
      {
        "risk_score_delta": float | None,
        "tier_change": str,
        "trajectory_change": str,
        "dominant_distress_delta": float | None,
        "direction": "improved" | "no_change" | "worsened" | "unknown"
      }
    """
    b_score = baseline.get("risk_score")
    f_score = followup.get("risk_score")
    score_delta: Optional[float] = None
    if b_score is not None and f_score is not None:
        score_delta = round(float(f_score) - float(b_score), 4)

    b_tier = str(baseline.get("risk_tier", "unknown")).lower()
    f_tier = str(followup.get("risk_tier", "unknown")).lower()
    tier_change = f"{b_tier}->{f_tier}"

    b_traj = str(baseline.get("trajectory_label", "unknown")).lower()
    f_traj = str(followup.get("trajectory_label", "unknown")).lower()
    trajectory_change = f"{b_traj}->{f_traj}"

    b_distress = baseline.get("dominant_distress_score")
    f_distress = followup.get("dominant_distress_score")
    distress_delta: Optional[float] = None
    if b_distress is not None and f_distress is not None:
        distress_delta = round(float(f_distress) - float(b_distress), 4)

    b_tier_rank = TIER_ORDER.get(b_tier, 0)
    f_tier_rank = TIER_ORDER.get(f_tier, 0)

    b_traj_rank = TRAJECTORY_ORDER.get(b_traj, 0)
    f_traj_rank = TRAJECTORY_ORDER.get(f_traj, 0)

    # Determine direction
    if b_tier_rank == 0 and f_tier_rank == 0 and score_delta is None:
        direction = "unknown"
    elif f_tier_rank < b_tier_rank and b_tier_rank > 0:
        # Tier decreased (e.g. high -> medium)
        direction = "improved"
    elif f_tier_rank > b_tier_rank and b_tier_rank > 0:
        # Tier increased (e.g. medium -> high)
        direction = "worsened"
    else:
        # Tier is identical: evaluate trajectory
        if f_traj_rank > b_traj_rank and b_traj_rank > 0:
            direction = "improved"
        elif f_traj_rank < b_traj_rank and f_traj_rank > 0:
            direction = "worsened"
        elif score_delta is not None:
            # Evaluate continuous risk score change
            if score_delta <= -0.01:
                direction = "improved"
            elif score_delta >= 0.01:
                direction = "worsened"
            else:
                direction = "no_change"
        else:
            direction = "no_change"

    return {
        "risk_score_delta": score_delta,
        "tier_change": tier_change,
        "trajectory_change": trajectory_change,
        "dominant_distress_delta": distress_delta,
        "direction": direction,
    }


def weeks_to_improvement(
    baseline: Dict[str, Any],
    risk_history: List[Dict[str, Any]],
    trajectory_history: List[Dict[str, Any]],
) -> Optional[int]:
    """
    Computes the elapsed weeks to the first documented positive improvement after baseline.

    Condition:
      The first week index after baseline_week where:
        - The risk tier is lower than the baseline tier, OR
        - The trajectory becomes 'stable' or 'improving' (when baseline was 'volatile' or 'declining').

    Returns:
      Elapsed weeks (int) or None if no improvement has been achieved yet.
    """
    baseline_week = int(baseline.get("week_index") or 0)
    b_tier_rank = TIER_ORDER.get(str(baseline.get("risk_tier", "unknown")).lower(), 0)
    b_traj = str(baseline.get("trajectory_label", "unknown")).lower()

    # Index trajectories by week_index
    traj_by_week = {
        int(t.get("week_index", 0)): str(t.get("trajectory_label", "unknown")).lower()
        for t in trajectory_history
        if t.get("week_index") is not None
    }

    # Evaluate risk assessments chronologically
    sorted_risk = sorted(
        [r for r in risk_history if int(r.get("week_index", 0)) > baseline_week],
        key=lambda r: int(r.get("week_index", 0)),
    )

    for r in sorted_risk:
        w_idx = int(r.get("week_index", 0))
        r_tier_rank = TIER_ORDER.get(str(r.get("risk_tier", "unknown")).lower(), 0)
        t_label = traj_by_week.get(w_idx, "")

        is_tier_improved = (b_tier_rank > 0 and r_tier_rank > 0 and r_tier_rank < b_tier_rank)
        is_traj_improved = (
            b_traj in {"declining", "volatile", "unknown"}
            and t_label in {"stable", "improving"}
        )

        if is_tier_improved or is_traj_improved:
            elapsed = w_idx - baseline_week
            return max(elapsed, 1)

    return None


def build_observed_change_text(
    delta: Dict[str, Any],
    category: str,
    weeks_to_improvement: Optional[int] = None,
    helpfulness_rating: Optional[int] = None,
) -> str:
    """
    Constructs a concise, PII-free templated summary string of observed changes
    for the canonical intervention_outcomes collection (Component 4 feedback loop).
    Strictly enforced to be <= 500 characters and free from identifying information (CleanText).

    Format:
      "{category}; risk {before}->{after} ({tier_change}); trajectory {trajectory_change}; {weeks} weeks to improvement; student-rated helpfulness {rating}/5"
    """
    cat_clean = str(category).strip().lower()
    t_change = delta.get("tier_change", "unknown->unknown")
    traj_change = delta.get("trajectory_change", "unknown->unknown")

    parts = [f"{cat_clean}"]

    score_delta = delta.get("risk_score_delta")
    if score_delta is not None:
        parts.append(f"risk delta {score_delta:+.4f} ({t_change})")
    else:
        parts.append(f"tier {t_change}")

    parts.append(f"trajectory {traj_change}")

    if weeks_to_improvement is not None:
        parts.append(f"{weeks_to_improvement} weeks to improvement")

    if helpfulness_rating is not None:
        parts.append(f"student-rated helpfulness {helpfulness_rating}/5")

    observed_text = "; ".join(parts)
    # Enforce maximum 500 character constraint
    return observed_text[:500]

