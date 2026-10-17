# Experiment Tracking Log: Component 1 (Affective State Detection)

*All metrics in this log are evaluated on external proxy benchmarks (`test_proxy.csv`) and are strictly labelled **Proxy Test**. Real LMS domain evaluation will be conducted on `test_real.csv` during subsequent phases.*

---

## 1. Summary of Experiments

| Run ID | Model Architecture | Training Data | Sequence Length | Pos-Weight Clip | Best Epoch / C | Val Macro F1 | Test Proxy Macro F1 | Test Proxy ROC-AUC | GoEmotions Test F1 | Emotion-4 Test F1 | Notes |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `EXP-001` | **VADER Lexicon** | None (rule-based) | N/A | None | N/A | N/A | **0.5979** *(binary)* | 0.7657 *(binary)* | 0.5283 *(binary)* | 0.7180 *(binary)* | Evaluated as a coarse binary "any distress" baseline only. Cannot separate 5 fine-grained classes. |
| `EXP-002` | **TF-IDF + Logistic Regression** | All Proxy (Train: 47,284) | 1-2 ngrams (10k) | Balanced | C=1.0 | 0.4645 | **0.4721** | **0.8762** | 0.4437 | 0.5218 | Multi-label One-vs-Rest baseline. Decision thresholds tuned per-class on `val.csv`. |
| `EXP-003` | **TF-IDF + LogReg (Ablation)** | GoEmotions Only (Train: 41,813) | 1-2 ngrams (10k) | Balanced | C=1.0 | 0.3859 | **0.3694** | **0.7996** | 0.4285 | 0.2662 | Ablation: Dropping Emotion-4 causes severe drop in `exam_anxiety` (-23.1% F1) and `academic_helplessness` (-19.3% F1). |
| `EXP-004` | **DistilRoBERTa (Smoke Test)** | All Proxy (Subsample: 500) | 64 (99.95% cov) | 10.0 | Epoch 1 | 0.1327 | **0.1092** | **0.6730** | 0.0894 | 0.1438 | CPU local smoke test verifying BCEWithLogitsLoss, PyTorch loop, threshold tuning, and artifact generation end-to-end. |
| `EXP-005` | **DistilRoBERTa (Colab GPU Full)** | All Proxy (Train: 47,284) | 64 (99.95% cov) | 10.0 | Epoch 3 (scheduled) | *Pending Colab* | *Pending Colab* | *Pending Colab* | *Pending Colab* | *Pending Colab* | Configured in `notebooks/colab_train.ipynb`. Ready for Colab execution. |

---

## 2. Detailed Per-Class Breakdown (Proxy Test)

### 2.1 TF-IDF + Logistic Regression Baseline (`baseline_tfidf.json`)
- **Tuned Thresholds (on `val.csv`):** `exam_anxiety: 0.65`, `conceptual_confusion: 0.80`, `academic_helplessness: 0.65`, `course_frustration: 0.60`, `motivation_erosion: 0.70`
- **Overall Macro F1:** **0.4721** | **Macro ROC-AUC:** **0.8762**

| Target Distress Class | Precision | Recall | F1 Score | ROC-AUC | Support (`test_proxy`) |
|---|:---:|:---:|:---:|:---:|:---:|
| `exam_anxiety` | 0.6301 | 0.7121 | **0.6686** | 0.9492 | 323 |
| `conceptual_confusion` | 0.3032 | 0.3725 | **0.3343** | 0.8805 | 153 |
| `academic_helplessness` | 0.5574 | 0.6602 | **0.6044** | 0.9303 | 309 |
| `course_frustration` | 0.5153 | 0.5625 | **0.5379** | 0.8448 | 896 |
| `motivation_erosion` | 0.1917 | 0.2450 | **0.2151** | 0.7762 | 151 |

#### Segmentation by Source:
- **`goemotions_proxy` subset (N=5,253):** Macro F1 = **0.4437**
  - High performance on `course_frustration` (F1 = 0.5422) and `academic_helplessness` (F1 = 0.4459).
- **`emotion4_proxy` subset (N=703):** Macro F1 = **0.5218**
  - High performance on `exam_anxiety` (F1 = 0.8415) and `academic_helplessness` (F1 = 0.7302).

---

### 2.2 Ablation Study: Training on GoEmotions Only (`ablation_tfidf_goemotions.json`)
To measure the impact of the Emotion-4 tweets on overall model capability, we excluded Emotion-4 from training and evaluated against the exact same held-out `test_proxy.csv`.

| Metric | All Proxy Training (EXP-002) | GoEmotions-Only Training (EXP-003) | Delta ($\Delta$) |
|---|:---:|:---:|:---:|
| **Macro F1** | **0.4721** | **0.3694** | **-0.1027 (-21.8%)** |
| `exam_anxiety` F1 | 0.6686 | 0.4373 | **-0.2313 (-34.6%)** |
| `conceptual_confusion` F1 | 0.3343 | 0.3177 | -0.0166 (-5.0%) |
| `academic_helplessness` F1 | 0.6044 | 0.4112 | **-0.1932 (-32.0%)** |
| `course_frustration` F1 | 0.5379 | 0.4739 | -0.0640 (-11.9%) |
| `motivation_erosion` F1 | 0.2151 | 0.2071 | -0.0080 (-3.7%) |
| **Emotion-4 Subset F1** | **0.5218** | **0.2662** | **-0.2556 (-49.0%)** |

**Empirical Finding:** Emotion-4 tweets provide crucial pretraining support for `exam_anxiety` (fear proxy) and `academic_helplessness` (sadness proxy). Without Emotion-4, the model severely underperforms on acute fear and despair expressions.

---

### 2.3 VADER Binary Baseline (`baseline_vader.json`)
- **Evaluation Type:** Proxy Test (Binary "Any Distress")
- **Decision Rule:** `compound <= -0.05` indicates negative emotional distress
- **Accuracy:** 0.7579
- **Precision:** 0.5923
- **Recall:** 0.6036
- **F1 Score:** **0.5979**
- **ROC-AUC:** 0.7657
- **Limitation Note:** VADER operates as a general rule-based lexicon. It has no conceptual representation of pedagogy or academic domains and **cannot separate or classify the 5 fine-grained distress classes**.
