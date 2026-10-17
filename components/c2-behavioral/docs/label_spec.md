# C2 Label Specification (DRAFT, to be frozen before any model training)
Unit: one row per (code_module, code_presentation, id_student, week t), week = floor(date/7), date>=0 only (pre-course days excluded).
Engagement score: e_w = log1p(clicks in week w). Weeks inside the enrolment period with no clicks have e_w = 0 (zero-fill).
Course last week L = (module_presentation_length + 6)//7 - 1.
Enrolment end: non-withdrawn -> L. Withdrawn -> min(date_unregistration//7, L)  (censoring: weeks after it are never used).
Excluded students: Withdrawn with missing or negative date_unregistration; any student whose enrolment end < 0.
Label window: weeks t-3 .. t+3 (all inside enrolment period). Valid labels only for t >= 3.
slope = least-squares slope of e_w over the window ; resid_sd = standard deviation of residuals after removing mean and slope (NOT a coefficient of variation).
Rules, in priority order:
 1. volatile  : resid_sd >= 1.0 AND abs(slope) < 0.10
 2. declining : slope <= -0.20
 3. improving : slope >= +0.20
 4. stable    : otherwise
Dormant window: all 7 weeks have zero clicks. Excluded from training/evaluation (count reported). Inference policy: DORMANT_POLICY, undecided (supervisor).
Features use weeks t-5..t ONLY (causal). Label uses t-3..t+3 (offline). NOTE: weeks t-3..t are in both, so the model partly extrapolates its own past trend.
Module/course id is NEVER a model feature.
Split: train 2013B+2013J, validation 2014B, test 2014J; remove validation/test students seen in an earlier presentation.
Extra robustness: leave-CCC-out (CCC has no 2013 presentation). CV inside train: GroupKFold by id_student.
Thresholds provisional until supervisor confirms, then frozen in a commit before any model evaluation.
Claims allowed in the report: "reproduces a causal clicks-trend label"; withdrawal rate per predicted label is weak supporting evidence only. Not ground truth.

---
## FROZEN decisions (before any model evaluation unless stated)
- Label = clicks trend (e_w = log1p(clicks)); thresholds FROZEN: S_TREND 0.20, RESID_SD_HI 1.0, S_FLAT 0.10 (fixed before model training, never tuned).
- Dormant policy (inference, causal): if the last 7 weeks all have zero clicks, bypass the model and output trajectory_label "declining" with
  contributing_indicator "no_activity_7w" (student had clicks earlier) or "never_active" (no clicks since week 0). confidence = DORMANT_RULE_CONFIDENCE (0.86),
  an uncalibrated OULAD at-risk rate (Fail+Withdrawn share among such students), documented as rule-based. Reason: the contract has only 4 labels.
- Video ablation is deferred to pilot LMS data. OULAD has no video events (limitation).
- Result interpretation: the model reproduces a causal clicks-trend label; it does not prove true disengagement. Withdrawal analysis is weak supporting evidence only.
---

