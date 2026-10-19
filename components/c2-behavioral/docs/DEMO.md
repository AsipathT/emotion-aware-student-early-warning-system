# Component 2: Live Demonstration Guide

This guide provides an exact, reproducible live-demo script connecting Component 2 (Behavioral Engagement Trajectory) to the LMS backend API.

> [!IMPORTANT]
> **Sanity Check Notice**:
> The synthetic student cohort generated in this demo is strictly an integration, authentication, and contract sanity check—it is **not** evidence of model classification accuracy. Ground-truth evaluation of classification accuracy and generalization is established on the 204,607 real OULAD test windows (see [reports/metrics/model_eval.json](../reports/metrics/model_eval.json)).

---

## 1. Prerequisites

1. Active Python virtual environment for the LMS backend (`backend/.venv`) and Component 2 (`components/c2-behavioral/.venv`).
2. The backend connects to the shared MongoDB Atlas database using its configured connection (do not print or copy any credentials).
3. Preshared Component API key placeholder (must be at least 24 characters, never use real production secrets):
   `c2_demo_secret_api_key_placeholder_2026`

---

## 2. Numbered Live Demo Steps

### Step 1: Start the LMS Backend

In **Terminal 1** (from repository root):

```powershell
# Set preshared component API key for C2 (placeholder, 24+ chars)
$env:COMPONENT_API_KEYS = '{"c2": "c2_demo_secret_api_key_placeholder_2026"}'

# Navigate to backend directory and start Uvicorn
cd backend
uvicorn app.main:app --port 8000
```

**What you should see**:
- Uvicorn startup messages confirming the application is listening on `http://127.0.0.1:8000`.
- MongoDB Atlas connection established and component key validation passing without errors.

---

### Step 2: Register and Login a Lecturer Account

If registration says the user already exists, skip it and just login.

In **Terminal 2** (PowerShell):

```powershell
# 2a. Register demonstration lecturer account
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/auth/register" `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{
    "email": "demo_lecturer@university.edu",
    "password": "Password123!",
    "full_name": "Demo Lecturer",
    "role": "lecturer"
  }'

# 2b. Login to obtain JWT Bearer Token
$loginRes = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/auth/login" `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{
    "email": "demo_lecturer@university.edu",
    "password": "Password123!"
  }'

$token = $loginRes.access_token
```

**What you should see**:
- Registration and login requests complete with HTTP 200/201 responses.
- A non-empty JWT bearer access token is returned and stored in `$token`.

---

### Step 3: Generate Synthetic Demonstration Cohort

> [!NOTE]
> Run the generator ONCE. Each run creates new synthetic pids (Python hash randomisation) and does not delete earlier synthetic identities/enrolments.

Generate a 12-student, 10-week cohort in dedicated course `DEMO_C2`:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/analytics/synthetic/generate" `
  -Headers @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
  } `
  -Body '{
    "course_id": "DEMO_C2",
    "num_students": 12,
    "num_weeks": 10,
    "cohort_profile": "balanced",
    "clear_existing": true
  }'
```

**What you should see**:
- A success JSON response with a message and counts (status code not verified).
- Summary payload confirming creation of 12 students across 10 academic weeks.

---

### Step 4: Run Component 2 Weekly Ingest (Dry-Run Mode with `--show`)

Activate the C2 venv first: `.\.venv\Scripts\Activate.ps1`

From `components/c2-behavioral/`:

```powershell
cd components/c2-behavioral

# Set LMS integration environment variables
$env:LMS_BASE_URL = "http://localhost:8000"
$env:C2_COMPONENT_KEY = "c2_demo_secret_api_key_placeholder_2026"

# Run classification for target week 9 with preview table and dry-run ingest
python scripts/run_week.py --course-id DEMO_C2 --week 9 --send --dry-run --show
```

**What you should see**:
- The export step fetches 120 weekly behavior records (12 students across 10 weeks).
- The pipeline summary shows 12 groups, with 12 classified trajectories and 0 skipped.
- A trajectory table with 12 rows (one per student), displaying PID suffix, clicks for the last 6 weeks, trajectory label, confidence (2 decimals), and contributing indicators.
- The LMS ingest summary shows Received 12 and Rejected 0 if everything is accepted.
- Label counts and confidences depend on the synthetic data and are not predetermined.

---

### Step 5: Live Write Mode (Optional `--no-dry-run`)

> [!WARNING]
> Live write is optional and may be rejected or conflict with the generator's own synthetic trajectory documents; the dry-run is the main demo.

```powershell
python scripts/run_week.py --course-id DEMO_C2 --week 9 --send --no-dry-run --show
```

**What you should see**:
- LMS ingest response summary reports `Dry run: False`, with Received 12 and Rejected 0 if accepted.

---

## 3. "If X Fails" Fallbacks

### Fallback A: Database / Network Connectivity Unavailable
If MongoDB Atlas or the LMS backend cannot be started during the demo, refer to the verified offline evaluation figures in `reports/figures/` and metrics in `reports/metrics/`:

- `reports/figures/fig1_model_comparison.png`: Bar chart of test split macro-F1 across Majority baseline (0.130), B2 rule baseline (0.228), B1 static baseline (0.382), and C2 model (0.504).
- `reports/figures/fig2_confusion_c2_test.png`: Row-normalized confusion matrix heatmap of the C2 model on the test split (per-class test F1: declining 0.634, improving 0.563, stable 0.499, volatile 0.320).
- `reports/figures/fig3_label_distribution.png`: Bar chart of trajectory label shares in non-dormant OULAD windows (stable 37.3%, declining 32.1%, improving 17.6%, volatile 13.0%).
- `reports/figures/fig4_ablation.png`: Feature ablation study on the test split (clicks only: 0.501, clicks + activity: 0.502, full features: 0.504).

Confidence distribution metrics on the 204,607 test windows ([reports/metrics/confidence_quantiles.json](../reports/metrics/confidence_quantiles.json)): median 0.530, mean 0.561, p25 0.441, p75 0.656.

### Fallback B: Standalone Inference Service (`POST /classify`)
If LMS ingest routes are unavailable, demonstrate Component 2 using its standalone FastAPI inference service with the verified 120-record sample request:

1. Launch the standalone service:
   ```powershell
   cd components/c2-behavioral
   uvicorn service.app:app --port 8100
   ```
   *(Note: The model file `models/c2_deploy.joblib` must exist; it is git-ignored and can be recreated by running `python scripts/deploy_eval.py`).*

2. In another terminal, invoke `POST /classify` using the sample request fixture:
   ```powershell
   Invoke-RestMethod -Method Post -Uri "http://localhost:8100/classify" `
     -ContentType "application/json" `
     -InFile "reports/samples/classify_request_sample.json"
   ```

**What you should see**:
- HTTP 200 response with an envelope containing `source: "c2"`, `schema_version: "1.0"`, and 12 classified trajectory items matching the 12 students.
