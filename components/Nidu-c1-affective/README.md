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

## 8. Progress checklist

- [ ] Taxonomy and labelling guide written
- [ ] Datasets cleaned and label mapping documented
- [ ] Domain dataset built and reviewed
- [ ] Baselines trained and evaluated
- [ ] Main model trained and evaluated
- [ ] Explainability added
- [ ] API wrapper integrated with the platform
- [ ] Demo ready for PP1

---

## 9. Run tests

```powershell
pytest tests
```