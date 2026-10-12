# MongoDB Schema Analysis against Platform Owner's Work

## Existing Collections in `origin/feature/Nidu-admin-panel`
From `backend/app/db/collections.py`, the following central collections exist:
- `users`
- `courses`
- `modules`
- `enrollments`
- `profiles`
- `activity_events`
- `messages`
- `attendance_records`
- `gradebook_entries`
- `behavioral_weekly`
- `affective_weekly`
- `engagement_trajectories`
- `risk_assessments`
- `recommendations`
- `interventions`
- `intervention_outcomes`
- `schema_migrations`
- `ingestion_runs`
- `identity_vault`
- `consent_notices`
- `consent_records`
- `audit_logs`

## Comparison with Needed Collections

| Needed Collection | Exists in Platform? | Differences & Notes |
| :--- | :--- | :--- |
| `assignments` | No | Need to use my ported models. |
| `assignment_submissions` | No | Need to use my ported models. |
| `quizzes` | No | Need to use my ported models. |
| `quiz_attempts` | No | Need to use my ported models. |
| `gradebook_entries` | Yes | Existing is `gradebook_entries`. |
| `attendance_sessions` | No | Need to use my ported models. |
| `attendance_records` | Yes | Existing is `attendance_records`. |
| `user_sessions` | No | Need to use my ported models. |
| `click_events` | Yes (`activity_events`) | Replaces `click_events`. Name conflict. |
| `weekly_features` | No (mapped to `behavioral_weekly`?) | Replaces `weekly_features`. Name conflict. |
| `affect_weekly` | Yes (`affective_weekly`) | Existing is `affective_weekly`. Name conflict. |
| `trajectory_labels` | Yes (`engagement_trajectories`) | Existing is `engagement_trajectories`. Name conflict. |
| `risk_scores` | Yes (`risk_assessments`) | Existing is `risk_assessments`. Name conflict. |
| `synthetic_ground_truth`| No | Need to use my ported models. |

## Pseudonymization Utility
- The platform owner has implemented `pseudonymize` in `backend/app/core/privacy.py`.
- **Difference:** The official one prefixes with `"STU_"` and takes the first 8 characters, whereas my ported version in `pseudonym.py` prefixes with `"pseudo_"` and takes 10 characters.
- **Action Required:** I must delete my `backend/app/core/pseudonym.py` and import `pseudonymize` from `app.core.privacy`.

