# C1: Student Affective State Detection

Component 1 of the **AI-Driven Early Warning System for Student Dropout in Higher Education** (J26-IT-349, SLIIT).

C1 reads student text from the LMS (forum posts, chat, journal entries), detects academic distress, and sends a weekly affective profile to the platform. Component 2 (trajectory) and Component 3 (risk prediction) use that profile as an input.

**Owner:** Nidu  |  **Status:** in development (PP1 preparation)

---

## 1. What this component does

| | |
|---|---|
| **Input** | Pseudonymised, consent-filtered student messages from the platform export API |
| **Output** | Per student, per course, per week: five emotion scores, a stress label, a confidence value, and the top words behind the decision |
| **Delivery** | `POST /api/v1/ingest/affective` with the C1 component key |

### Distress taxonomy (5 classes)

| Class | Meaning | Example |
|---|---|---|
| `exam_anxiety` | Fear or worry about exams or deadlines | "I'm terrified I'll fail the exam." |
| `conceptual_confusion` | Not understanding course content | "I still don't get how recursion works." |
| `academic_helplessness` | Feeling unable to succeed whatever they do | "There's no point, I can't do this course." |
| `course_frustration` | Anger or irritation with the course | "This assignment is badly explained." |
| `motivation_erosion` | Loss of interest or drive | "I've stopped caring about this module." |

> Add 3 to 5 real-style examples per class in `docs/taxonomy.md` and keep the labelling rules there.

---

## 2. Folder structure

```
components/Nidu-c1-affective/
├── data/
│   ├── raw/         original datasets (git-ignored)
│   ├── interim/     cleaned or mapped data (git-ignored)
│   └── processed/   train / validation / test splits (git-ignored)
├── models/          trained weights and checkpoints (git-ignored)
├── notebooks/       exploration and experiments
├── src/             reusable code (preprocessing, training, inference, API)
├── tests/           unit tests
├── requirements.txt
├── .env.example
└── README.md
```

Data and models are never committed. See `data/README.md` for where to get each dataset.

---

## 3. Setup

Use Python 3.10 to 3.12 for training (best library compatibility).

```powershell
cd components\Nidu-c1-affective
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then fill in your values
```

If you have an NVIDIA GPU, install PyTorch first using the command from https://pytorch.org, then run `pip install -r requirements.txt`. Without a GPU, train on Google Colab or Kaggle.

Notebooks: run `nbstripout --install` once so outputs (which may contain student text) are stripped before every commit.

---

## 4. Data

| Dataset | Use | Notes |
|---|---|---|
| GoEmotions | Pretraining (28 emotions, mapped to the 5 classes) | Weak proxy, not educational text |
| 4-class emotion dataset (`eng_dataset.csv`) | Extra pretraining | Mostly tweets; not the original ISEAR |
| Domain set (self-built) | Fine-tuning and testing | Education-specific messages, reviewed by hand |
| OULAD | Not used for text | Click data only; used by other components |

Real LMS messages are used only with student consent and after `scrub_text()` removes personal data.

### Split Note
- The proxy data pipeline produces `data/processed/train.csv`, `data/processed/val.csv`, and `data/processed/test_proxy.csv` derived from normalized external corpora (GoEmotions and Emotion-4).
- `test_real.csv` will be a separate, human-written benchmark set containing authentic higher-education LMS communications. It is strictly held out and will never be mixed into `train.csv`, `val.csv`, or `test_proxy.csv`.

---

## 5. Pipeline

1. **Preprocess:** clean text, map labels, build train/validation/test splits.
2. **Baselines:** VADER lexicon and RoBERTa trained on GoEmotions only.
3. **Main model:** transformer encoder plus linguistic-marker features, fused before the classifier.
4. **Explain:** SHAP or attention highlights the words behind each prediction.
5. **Serve:** FastAPI wrapper that reads from the export API and posts to the ingest API.

### Metrics

Macro F1, per-class precision and recall, AUC-ROC, and a confusion matrix. Targets are listed in the project proposal. Report results on the held-out test set only.

---

## 6. Platform integration

The authoritative schema is in `contracts/v1/` and `contracts/CONTRACT.md`. Never edit those files from this component. Use `scripts/send_sample_ingest.py` for a working example.

- **Read:** `GET /api/v1/export/messages` (consenting students only, pseudonymised IDs)
- **Write:** `POST /api/v1/ingest/affective` with header `X-Component-Key`

Illustrative record (check the contract for the exact fields):

```json
{
  "pid": "STU_xxxxxxxx",
  "course_id": "CS101",
  "week_index": 2,
  "emotion_scores": {
    "exam_anxiety": 0.85,
    "conceptual_confusion": 0.10,
    "academic_helplessness": 0.02,
    "course_frustration": 0.02,
    "motivation_erosion": 0.01
  },
  "stress_label": "exam_anxiety",
  "confidence": 0.92,
  "message_count": 5,
  "top_drivers": [{"token_or_marker": "struggling", "weight": 0.78}]
}
```

---

## 7. Privacy and ethics

- Work only with pseudonymised IDs (`STU_xxxxxxxx`). Do not try to identify students.
- Never commit data, model weights, `.env` files, or notebook outputs containing student text.
- Never connect directly to the platform database. Use the APIs.
- Output is decision support for counsellors, not an automatic judgement of a student.

---

---

## 8. Interactive Demo & Probe Evaluation

### Launch the Streamlit Demonstration App
```powershell
cd components\Nidu-c1-affective
.venv\Scripts\activate
streamlit run demo/app.py
```
**Features included in Demo:**
- Interactive text analysis using fine-tuned DistilRoBERTa (`models/checkpoint-best`) on CPU.
- Visual score bars with calibrated validation thresholds for all 5 distress categories.
- Feature attribution highlighting influential tokens via leave-one-word-out occlusion (no SHAP dependency).
- Side-by-side contrast against the generic VADER sentiment lexicon.
- Dry-run `AffectiveWeeklyVector` record generator validated against `contracts/v1/AffectiveWeeklyVector.json`.
- "Live from LMS" message stream viewer (active when `C1_COMPONENT_KEY` is set).

### Run Domain Probe Evaluation
```powershell
python src/probe_eval.py --input data/interim/domain_reviewed_DRAFT.csv.csv
```

---

## 9. Progress checklist

- [x] Taxonomy and labelling guide written (`docs/taxonomy.md`, `docs/annotation_guide.md`)
- [x] Datasets cleaned and label mapping documented (`src/label_map.yaml`)
- [x] Domain dataset built and reviewed templates created (`src/data/make_domain_template.py`, `src/data/split_reviewed.py`)
- [x] Baselines trained and evaluated (`baseline_tfidf.json`, `baseline_vader.json`)
- [x] Main model trained and evaluated on proxy test (`distilroberta_full.json`, Macro F1: 0.5648)
- [x] Explainability added via word occlusion
- [ ] API wrapper integrated with the platform
- [x] Demo ready for PP1 (`demo/app.py`)

---

## 10. Run tests

```powershell
pytest tests
```