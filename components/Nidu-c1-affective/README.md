# C1: Student Affective State Detection

Component 1 of the **AI-Driven Early Warning System for Student Dropout in Sri Lankan Higher Education** (Project ID **J26-IT-349**, SLIIT, IT4010 Research Project).

C1 reads student text from the LMS (forum posts, chat, journal entries), detects academic distress, and prepares a weekly affective profile for the platform. Component 2 (behavioural trajectory) and Component 3 (dropout risk prediction) use that profile as an input.

| | |
|---|---|
| **Owner** | Asipath T.M.N.V (IT23145870) |
| **Status** | PP1 complete: model trained and evaluated, explainable demo running, contract validated. Ingest API wrapper is the next step. |
| **Main model** | Fine-tuned `distilroberta-base`, multi-label, 5 classes |
| **Final test result** | Macro F1 **0.5648**, macro ROC-AUC **0.9394** (public proxy test set) |

---

## 1. What this component does

| | |
|---|---|
| **Input** | Pseudonymised, consent-filtered, PII-scrubbed student messages from the platform export API |
| **Output** | Per student, per course, per week: five emotion scores, a stress label, a confidence value, message count, and the top words behind the decision |
| **Delivery** | `POST /api/v1/ingest/affective` with the C1 component key (**planned**, see Section 9). Today the record is generated and validated as a dry run. |

### Distress taxonomy (5 classes)

| Class | Meaning | Example |
|---|---|---|
| `exam_anxiety` | Fear or worry about exams or deadlines | "I'm terrified I'll fail the exam." |
| `conceptual_confusion` | Not understanding course content | "I still don't get how recursion works." |
| `academic_helplessness` | Feeling unable to succeed whatever they do | "There's no point, I can't do this course." |
| `course_frustration` | Anger or irritation with the course | "This assignment is badly explained." |
| `motivation_erosion` | Loss of interest or drive | "I've stopped caring about this module." |

The labelling rules and more examples are in `docs/taxonomy.md` and `docs/annotation_guide.md`. A message can belong to several classes at once, so the task is **multi-label**.

---

## 2. Folder structure

```
components/Nidu-c1-affective/
├── data/
│   ├── raw/         original datasets (git-ignored)
│   ├── interim/     cleaned or mapped data (git-ignored)
│   └── processed/   train / val / test splits (git-ignored)
├── demo/            Streamlit demonstration app (app.py)
├── docs/            taxonomy, annotation guide
├── models/          trained checkpoint and thresholds (git-ignored)
├── notebooks/       Colab training notebook and experiments
├── reports/
│   ├── metrics/     evaluation JSON files
│   └── figures/     training curve, per-class chart, confusion matrix
├── src/             preprocessing, training, evaluation, probe, LMS client
├── tests/           unit tests
├── .streamlit/      Streamlit configuration
├── requirements.txt / requirements-lock.txt
├── .env.example
└── README.md
```

Data and model weights are never committed. See `data/README.md` for where to obtain each dataset.

---

## 3. Setup

Use Python 3.10 to 3.12.

```powershell
cd components\Nidu-c1-affective
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then fill in your values
```

Training needs a GPU. If you do not have one, train on Google Colab (Section 5). Inference and the demo run on CPU.

Notebooks: run `nbstripout --install` once so outputs (which may contain student text) are stripped before every commit.

---

## 4. Data

| Dataset | Use | Notes |
|---|---|---|
| **GoEmotions** (Reddit comments, 28 emotions) | Main training source | Mapped to the 5 classes with `src/label_map.yaml`. A weak proxy, not educational text. |
| **4-class emotion dataset** (`eng_dataset.csv`, tweets) | Second training source | Mostly tweets; not the original ISEAR. Supports only some of the 5 classes. |
| **Domain probe set** (self-built) | Evaluation only, never used for training | 140 education-style sentences, **AI-drafted**, used to check domain transfer. |
| **OULAD** | Not used by C1 | Click data only; used by other components. |
| **LMS messages** | Inference and demo only | Used only with student consent, after `scrub_text()` removes personal data. |

### Splits (proxy data)

| Split | Samples |
|---|---|
| `train.csv` | 47,284 |
| `val.csv` | 5,943 |
| `test_proxy.csv` | 5,956 |

Duplicates and train/test leakage are removed during preparation. Class weights are computed from the training set (clipped at 10.0) to handle class imbalance.

`test_real.csv` is planned as a separate, human-written benchmark of authentic LMS communication. It will be strictly held out and never mixed into the files above.

---

## 5. Method

1. **Preprocess:** clean text, deduplicate, remove leakage, map public-dataset labels to the 5 classes, build train/validation/test splits.
2. **Baselines:** TF-IDF classifier and the VADER lexicon.
3. **Main model:** fine-tuned `distilroberta-base` with 5 independent sigmoid outputs.
   - Loss: `BCEWithLogitsLoss` with per-class positive weights.
   - Max sequence length 64, batch size 32, learning rate 2e-5, seed 42.
   - After every epoch, **per-class decision thresholds are tuned on the validation set** (grid 0.10 to 0.90) and the checkpoint with the best validation macro F1 is kept.
   - The test set is used once, at the end.
4. **Explain:** leave-one-word-out occlusion. Each word is removed in turn, and the drop in the class probability is that word's importance. No SHAP dependency.
5. **Contract:** a weekly affective vector is built per student and validated with `jsonschema` against `contracts/v1/AffectiveWeeklyVector.json`.

### Training environment

Training was run on **Google Colab (Tesla T4 GPU)** because fine-tuning on a laptop CPU is too slow. Code and data live on Google Drive, and the checkpoint was reloaded on CPU to confirm the metrics reproduce. The notebook is in `notebooks/colab_train.ipynb`. Typical command:

```bash
python -m src.train --epochs 50 --batch-size 32 --lr 2e-5 --seed 42 --run-name epochs50
```

A run with `--run-name` writes to its own folder and `reports/metrics/<run-name>.json`, so it cannot overwrite earlier results. `--max-samples` gives a quick smoke test.

---

## 6. Results

All numbers below are on the **public proxy test set** (`test_proxy.csv`, 5,956 samples).

### Final model

Best checkpoint: epoch 2 of a 50-epoch run (validation macro F1 0.5782), selected on validation data only.

| Class | Threshold | F1 | AUC |
|---|---|---|---|
| exam_anxiety | 0.90 | 0.7453 | 0.9789 |
| conceptual_confusion | 0.70 | 0.4373 | 0.9568 |
| academic_helplessness | 0.90 | 0.7043 | 0.9654 |
| course_frustration | 0.75 | 0.6271 | 0.9085 |
| motivation_erosion | 0.50 | 0.3100 | 0.8872 |
| **Macro** | | **0.5648** | **0.9394** |

By source: `goemotions_proxy` macro F1 0.4985, `emotion4_proxy` macro F1 0.5147.

![Per-class F1 and AUC](reports/figures/per_class_f1_auc_epochs50.png)

### Model comparison (macro F1, test)

| Model | Training data | Macro F1 |
|---|---|---|
| **DistilRoBERTa (final)** | GoEmotions + emotion-4 | **0.5648** |
| TF-IDF baseline | GoEmotions + emotion-4 | 0.4721 |
| DistilRoBERTa (ablation) | GoEmotions only | 0.4557 |
| TF-IDF (ablation) | GoEmotions only | 0.3694 |
| VADER | Generic sentiment lexicon | Cannot separate the 5 classes; shown side by side in the demo |

DistilRoBERTa beats the classical baseline in both settings, and adding the second data source improves generalisation. Other transformer encoders (for example DistilBERT, BERT-base, MiniLM) have **not** been compared yet; see Section 9.

### Training behaviour

A 50-epoch run was used to check convergence. Training loss kept falling (0.52 to 0.019) while validation macro F1 peaked at epoch 2 and then declined, which is overfitting. Best-checkpoint selection on validation F1 therefore keeps epoch 2. The same result (macro F1 0.5648) was obtained in an earlier 3-epoch run, which confirms reproducibility.

![Training curve](reports/figures/c1_training_curve_50_epochs.png)

### Domain probe (education-style text)

The 140-sentence probe set (AI-drafted) was used to check how the proxy-trained model behaves on student-style language. Overall recall was 43 of 105 positive sentences (41%) with 50 false alarms. Per-class recall: `exam_anxiety` 12/15, `conceptual_confusion` 13/30, `academic_helplessness` 1/15, `course_frustration` 6/15, `motivation_erosion` 11/30. This shows a **domain gap**, especially for `academic_helplessness`, and motivates domain adaptation (Section 9).

---

## 7. Interactive demo

```powershell
cd components\Nidu-c1-affective
.venv\Scripts\activate
streamlit run demo\app.py
```

The app opens at `http://localhost:8501`. If that port is busy, Streamlit picks the next one (for example 8502).

**Tab 1: Interactive Text Analysis**
1. Type or choose an example message.
2. Predicted distress state and the five scores with their tuned thresholds.
3. Word-occlusion highlighting and top driver tokens.
4. Weekly record preview with a **Contract Check** against `contracts/v1/AffectiveWeeklyVector.json`. The raw JSON is available in a collapsed *Technical view* panel.
5. Side panel: VADER generic sentiment, to show why a 5-class model is needed.

**Tab 2: Live from LMS (Export Feed)**
- Requires `C1_COMPONENT_KEY` (environment variable or entered in the app). `LMS_BASE_URL` defaults to `http://localhost:8000`.
- Fetches up to 500 scrubbed messages from `GET /api/v1/export/messages`, newest first, with filters by PID, source type and distress alerts.
- Predicts per message, then aggregates a weekly dry-run record per student PID.

### Probe evaluation

```powershell
python src/probe_eval.py --input data/interim/domain_reviewed_DRAFT.csv.csv
```

---

## 8. Platform integration

The authoritative schema is in `contracts/v1/` and `contracts/CONTRACT.md`. Never edit those files from this component. Use `scripts/send_sample_ingest.py` for a working example.

- **Read:** `GET /api/v1/export/messages` (consenting students only, pseudonymised IDs, header `X-Component-Key`)
- **Write (planned):** `POST /api/v1/ingest/affective` with header `X-Component-Key`

Example record (the contract defines the exact fields):

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

## 9. Progress, limitations and next steps

### Progress

- [x] Taxonomy and labelling guide (`docs/taxonomy.md`, `docs/annotation_guide.md`)
- [x] Datasets cleaned, leakage removed, label mapping documented (`src/label_map.yaml`)
- [x] Domain probe set built and evaluated (`src/data/`, `src/probe_eval.py`)
- [x] Baselines trained and evaluated (TF-IDF, VADER)
- [x] Main model trained on Colab GPU and evaluated (macro F1 0.5648, AUC 0.9394)
- [x] 50-epoch convergence experiment with best-checkpoint selection
- [x] Explainability by word occlusion
- [x] Weekly vector validated against the platform contract
- [x] Demo with live LMS export feed (PP1)
- [ ] Weekly aggregation and `POST /api/v1/ingest/affective` wrapper
- [ ] Domain adaptation with student-style text and a human-written `test_real.csv`
- [ ] Comparison with other transformer encoders

### Limitations

- The model is trained on **public proxy data**, not real student text. Every score in Section 6 is on a proxy test set and will not transfer one-to-one to real LMS messages.
- The domain probe set is small and AI-drafted; `academic_helplessness` performs poorly on it.
- `motivation_erosion` and `conceptual_confusion` are the weakest classes.
- The stress label in the demo is the first class (in taxonomy order) that exceeds its threshold, not the highest-scoring class.
- Messages are truncated at 64 tokens.
- C1 output is **decision support for counsellors**, not an automatic judgement of a student.

### Next steps

1. Implement weekly aggregation and the ingest wrapper so C1 output reaches C2 and C3 through the contract.
2. Fine-tune and evaluate on student-style data, with a held-out human-written test set.
3. Compare further encoders (DistilBERT, BERT-base, MiniLM) against the current model.

---

## 10. Privacy and ethics

- Work only with pseudonymised IDs (`STU_xxxxxxxx`). Do not try to identify students.
- Only students with an active, accepted consent record are exported by the platform; text is scrubbed of personal data before it reaches C1.
- Never commit data, model weights, `.env` files, or notebook outputs containing student text.
- Never connect directly to the platform database. Use the APIs.
- Predictions support human review and are not a diagnosis.

---

## 11. Run tests

```powershell
pytest tests
```