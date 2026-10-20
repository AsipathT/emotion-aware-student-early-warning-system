# Experiment Tracking Log: Component 1 (Affective State Detection)

> [!IMPORTANT]
> **Evaluation Type Notice:** All metrics in this log are evaluated on external proxy benchmarks (`test_proxy.csv`, N=5,956) and are strictly labelled **Proxy Test**. Real LMS domain evaluation will be conducted on `test_real.csv` during subsequent phases. No real student data is claimed in these benchmark results.

---

## 1. Summary of Experiments (All Evaluated on Proxy Test)

| Run ID | Model Architecture | Training Data | Sequence Length | Pos-Weight Clip | Best Epoch / C | Val Macro F1 | Test Proxy Macro F1 | Test Proxy ROC-AUC | Reddit-Only (GoEmotions) F1 | Tweets-Only (Emotion-4) Supported F1* | Notes |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `EXP-001` | **VADER Lexicon** | None (rule-based) | N/A | None | N/A | N/A | **0.5979** *(binary)* | 0.7657 *(binary)* | 0.5283 *(binary)* | 0.7180 *(binary)* | Evaluated as a coarse binary "any distress" baseline only. Cannot separate 5 fine-grained classes. |
| `EXP-002` | **TF-IDF + Logistic Regression** | All Proxy (Train: 47,284) | 1-2 ngrams (10k) | Balanced | C=1.0 | 0.4645 | **0.4721** | **0.8762** | 0.4249 | 0.7133 | Multi-label One-vs-Rest baseline. Decision thresholds tuned per-class on `val.csv`. |
| `EXP-003` | **TF-IDF + LogReg (Ablation)** | GoEmotions Only (Train: 41,813) | 1-2 ngrams (10k) | Balanced | C=1.0 | 0.3859 | **0.3694** | **0.7996** | 0.4253 | 0.3180 | Ablation: Dropping Emotion-4 drops `exam_anxiety` (-34.6% F1) and `academic_helplessness` (-32.0% F1). |
| `EXP-004` | **DistilRoBERTa (Smoke Test)** | All Proxy (Subsample: 500) | 64 (99.95% cov) | 10.0 | Epoch 1 | 0.1327 | **0.1092** | **0.6730** | 0.1092 | N/A | CPU local smoke test verifying BCEWithLogitsLoss, PyTorch loop, threshold tuning, and artifact generation end-to-end. |
| `EXP-005` | **DistilRoBERTa (Full Run)** | All Proxy (Train: 47,284) | 64 (99.95% cov) | 10.0 | Epoch 2 / 3 | **0.5401** | **0.5648** | **0.9394** | **0.4985** | **0.8578** | Best full model checkpoint (`checkpoint-best/`). Reproduces exactly on CPU (diff: 0.000000). |
| `EXP-006` | **DistilRoBERTa (Ablation)** | GoEmotions Only (Train: 41,813) | 64 (99.95% cov) | 10.0 | Epoch 2 / 3 | 0.4412 | **0.4557** | **0.8821** | N/A | N/A | Ablation run (Colab log). Confirms Emotion-4 tweets are critical for acute distress representation. |

*\* Note on Tweets-Only Supported F1 (`macro_f1_supported_classes`): Emotion-4 contains only fear, anger, sadness, and joy annotations, which map to 3 target distress classes (`exam_anxiety`, `academic_helplessness`, `course_frustration`). The remaining 2 classes (`conceptual_confusion`, `motivation_erosion`) have 0 support in `emotion4_proxy`. Standard macro F1 averages over all 5 classes (penalizing 0-support classes with F1=0.0). `macro_f1_supported_classes` averages exclusively over classes with support > 0.*

---

## 2. Detailed Per-Class Breakdown (Proxy Test)

### 2.1 DistilRoBERTa Full Model (`distilroberta_full.json` & `checkpoint-best`)
- **Tuned Thresholds (on `val.csv`):** `exam_anxiety: 0.90`, `conceptual_confusion: 0.70`, `academic_helplessness: 0.90`, `course_frustration: 0.75`, `motivation_erosion: 0.50`
- **Overall Macro F1:** **0.5648** | **Macro ROC-AUC:** **0.9394** | **Exact Match Ratio:** **0.7691**

| Target Distress Class | Precision | Recall | F1 Score | ROC-AUC | Support (`test_proxy`) | Applied Threshold |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `exam_anxiety` | 0.6962 | 0.8019 | **0.7453** | 0.9789 | 323 | 0.90 |
| `conceptual_confusion` | 0.3694 | 0.5359 | **0.4373** | 0.9568 | 153 | 0.70 |
| `academic_helplessness` | 0.6657 | 0.7476 | **0.7043** | 0.9654 | 309 | 0.90 |
| `course_frustration` | 0.5788 | 0.6842 | **0.6271** | 0.9085 | 896 | 0.75 |
| `motivation_erosion` | 0.2281 | 0.4834 | **0.3100** | 0.8872 | 151 | 0.50 |

#### Segmentation by Source:
- **`goemotions_proxy` subset (Reddit, N=5,247):**
  - **Macro F1:** **0.4985** | **Macro ROC-AUC:** **0.9305**
  - Per-class: `exam_anxiety`: 0.5896, `conceptual_confusion`: 0.4420, `academic_helplessness`: 0.5673, `course_frustration`: 0.5746, `motivation_erosion`: 0.3188
- **`emotion4_proxy` subset (Tweets, N=709):**
  - **Overall 5-class Macro F1:** **0.5147**
  - **Supported-Classes Macro F1 (`macro_f1_supported_classes`):** **0.8578** (zero-support classes `conceptual_confusion` and `motivation_erosion` excluded)
  - Per-class (supported): `exam_anxiety`: 0.8431, `academic_helplessness`: 0.8599, `course_frustration`: 0.8703

---

### 2.2 TF-IDF + Logistic Regression Baseline (`baseline_tfidf.json`)
- **Tuned Thresholds (on `val.csv`):** `exam_anxiety: 0.65`, `conceptual_confusion: 0.80`, `academic_helplessness: 0.65`, `course_frustration: 0.60`, `motivation_erosion: 0.70`
- **Overall Macro F1:** **0.4721** | **Macro ROC-AUC:** **0.8762** | **Exact Match Ratio:** **0.7312**

| Target Distress Class | Precision | Recall | F1 Score | ROC-AUC | Support (`test_proxy`) | Applied Threshold |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `exam_anxiety` | 0.6301 | 0.7121 | **0.6686** | 0.9492 | 323 | 0.65 |
| `conceptual_confusion` | 0.3032 | 0.3725 | **0.3343** | 0.8805 | 153 | 0.80 |
| `academic_helplessness` | 0.5574 | 0.6602 | **0.6044** | 0.9303 | 309 | 0.65 |
| `course_frustration` | 0.5153 | 0.5625 | **0.5379** | 0.8448 | 896 | 0.60 |
| `motivation_erosion` | 0.1917 | 0.2450 | **0.2151** | 0.7762 | 151 | 0.70 |

#### Segmentation by Source:
- **`goemotions_proxy` subset (Reddit, N=5,247):**
  - **Macro F1:** **0.4249** | **Macro ROC-AUC:** **0.8581**
  - Per-class: `exam_anxiety`: 0.5524, `conceptual_confusion`: 0.3434, `academic_helplessness`: 0.5101, `course_frustration`: 0.4957, `motivation_erosion`: 0.2229
- **`emotion4_proxy` subset (Tweets, N=709):**
  - **Overall 5-class Macro F1:** **0.4280**
  - **Supported-Classes Macro F1 (`macro_f1_supported_classes`):** **0.7133**
  - Per-class (supported): `exam_anxiety`: 0.7197, `academic_helplessness`: 0.7030, `course_frustration`: 0.7171

---

### 2.3 Model Comparison: TF-IDF vs DistilRoBERTa (Reddit-Only Subset)

On the Reddit-only (`goemotions_proxy`) proxy test set, where all 5 classes are naturally present with non-zero support, DistilRoBERTa consistently outperforms the TF-IDF linear baseline across every single category:

| Distress Class | TF-IDF (Reddit-Only) F1 | DistilRoBERTa (Reddit-Only) F1 | Delta ($\Delta$) | Relative Improvement |
|---|:---:|:---:|:---:|:---:|
| `exam_anxiety` | 0.5524 | 0.5896 | +0.0372 | +6.7% |
| `conceptual_confusion` | 0.3434 | 0.4420 | +0.0986 | **+28.7%** |
| `academic_helplessness` | 0.5101 | 0.5673 | +0.0572 | +11.2% |
| `course_frustration` | 0.4957 | 0.5746 | +0.0789 | +15.9% |
| `motivation_erosion` | 0.2229 | 0.3188 | +0.0959 | **+43.0%** |
| **Macro Average** | **0.4249** | **0.4985** | **+0.0736** | **+17.3%** |

*Visualisation available in `reports/figures/model_comparison.png`.*

---

### 2.4 Ablation Study: Impact of Emotion-4 Tweets

To investigate whether including Twitter emotion data is beneficial for pretraining affective distress detection, we trained models exclusively on GoEmotions proxy data (excluding Emotion-4) and evaluated on the identical held-out `test_proxy.csv`.

#### DistilRoBERTa Ablation:
| Target Distress Class | All Proxy Training (EXP-005) | GoEmotions-Only (EXP-006) | Delta ($\Delta$) |
|---|:---:|:---:|:---:|
| **Macro F1** | **0.5648** | **0.4557** | **-0.1091 (-19.3%)** |
| `exam_anxiety` | 0.7453 | 0.5333 | **-0.2120 (-28.4%)** |
| `conceptual_confusion` | 0.4373 | 0.4342 | -0.0031 (-0.7%) |
| `academic_helplessness` | 0.7043 | 0.4936 | **-0.2107 (-29.9%)** |
| `course_frustration` | 0.6271 | 0.5432 | -0.0839 (-13.4%) |
| `motivation_erosion` | 0.3100 | 0.2742 | -0.0358 (-11.5%) |
| **Macro ROC-AUC** | **0.9394** | **0.8821** | -0.0573 (-6.1%) |

#### TF-IDF Baseline Ablation:
| Target Distress Class | All Proxy Training (EXP-002) | GoEmotions-Only (EXP-003) | Delta ($\Delta$) |
|---|:---:|:---:|:---:|
| **Macro F1** | **0.4721** | **0.3694** | **-0.1027 (-21.8%)** |
| `exam_anxiety` | 0.6686 | 0.4373 | **-0.2313 (-34.6%)** |
| `conceptual_confusion` | 0.3343 | 0.3177 | -0.0166 (-5.0%) |
| `academic_helplessness` | 0.6044 | 0.4112 | **-0.1932 (-32.0%)** |
| `course_frustration` | 0.5379 | 0.4739 | -0.0640 (-11.9%) |
| `motivation_erosion` | 0.2151 | 0.2071 | -0.0080 (-3.7%) |

**Key Empirical Finding:**
Both model architectures confirm that Emotion-4 tweets provide crucial acute affective representations. Removing Emotion-4 causes dramatic degradation in `exam_anxiety` (-28.4% to -34.6%) and `academic_helplessness` (-29.9% to -32.0%), while having minimal effect on `conceptual_confusion` (which only exists in GoEmotions). Including Emotion-4 is therefore essential for robust proxy pretraining.

*Visualisation available in `reports/figures/ablation_comparison.png`.*

---

### 2.5 VADER Binary Baseline (`baseline_vader.json`)
- **Evaluation Type:** Proxy Test (Binary "Any Distress")
- **Decision Rule:** `compound <= -0.05` indicates distress
- **Accuracy:** 0.7579 | **Precision:** 0.5923 | **Recall:** 0.6036 | **F1 Score:** **0.5979** | **ROC-AUC:** 0.7657
- **Critical Architectural Limitation:** VADER operates as a general rule-based sentiment dictionary without any pedagogy or distress concepts. It **cannot separate or classify the 5 fine-grained educational distress classes**, serving only as a baseline floor for generic negative polarity.

---

## 3. Artifact Index

- **Model Checkpoints:** `models/checkpoint-best/` (weights & tokenizer), `models/thresholds.json`
- **Metric Files:**
  - `reports/metrics/distilroberta_full.json` (Full run metrics)
  - `reports/metrics/baseline_tfidf.json` (TF-IDF all-data)
  - `reports/metrics/ablation_tfidf_goemotions.json` (TF-IDF GoEmotions-only ablation)
  - `reports/metrics/baseline_vader.json` (VADER binary baseline)
- **Figures:**
  - `reports/figures/model_comparison.png` (TF-IDF vs DistilRoBERTa on Reddit subset)
  - `reports/figures/ablation_comparison.png` (All-data vs GoEmotions ablation)
  - `reports/figures/confusion_matrix_distilroberta.png` (5-panel confusion matrix)
