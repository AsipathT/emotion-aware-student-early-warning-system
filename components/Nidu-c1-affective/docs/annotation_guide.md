# Component 1 (C1): Student Affective State Annotation Guide

**Project:** J26-IT-349 "AI-Driven Early Warning System for Student Dropout in Higher Education"  
**Component:** C1 — Student Affective State Detection  
**Target Domain:** Higher Education Learning Management System (LMS) Forum Posts, Discussion Boards, and Direct Student Communications  
**Primary Goal:** Provide clear, reproducible instructions for human annotators to identify and tag academic emotional distress states in student text.

---

## 1. Ethical & Pedagogical Principles

1. **Non-Punitive Intent:** The affective detection model aims to provide early academic support, intervention, and empathy—never punitive grading or automated disciplinary profiling.
2. **Context-Aware Interpretation:** Student posts reflect real cognitive and emotional strain. Annotators must judge the text based on its expressed academic affect, not their personal judgment of student effort.
3. **Multi-Label Allowance:** Academic emotions frequently co-occur (e.g., confusion leading to frustration). Annotators should flag all distress classes that are genuinely supported by evidence in the text.
4. **Neutral/Non-Distress Default:** Informational queries, factual answers, and routine logistics without negative affective charge must be tagged as `"none"`.

---

## 2. Taxonomy of Distress Classes

Our taxonomy models five discrete, actionable educational distress states:

```
                    ┌───────────────────────────────┐
                    │  Student Affective Utterance  │
                    └───────────────┬───────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
┌──────────────────────┐                         ┌──────────────────────┐
│  Neutral / Logistics │                         │ Academic Distress    │
│      ("none")        │                         │ (1 to 5 classes)     │
└──────────────────────┘                         └──────────┬───────────┘
                                                            │
         ┌──────────────┬──────────────┬─────────────┬──────┴──────┐
         ▼              ▼              ▼             ▼             ▼
   [exam_anxiety]  [conceptual_   [academic_     [course_      [motivation_
                    confusion]    helplessness]  frustration]  erosion]
```

### 2.1 Class 1: `exam_anxiety`
* **Definition:** Anticipatory dread, acute tension, panic, or fear specifically oriented around upcoming assessments, exams, midterms, quizzes, or critical assignment deadlines.
* **Core Emotional Tone:** Fear, panic, acute stress, somatic anxiety symptoms.
* **Linguistic Indicators:** "terrified of the exam", "having panic attacks about tomorrow's test", "heart is racing looking at the midterm prep", "freaking out about the final", "I'm going to fail this exam".
* **Boundary Rules:**
  - Must relate to assessment pressure or deadline evaluation.
  - If the student is resigned to failure after the exam is already over and feels powerless, tag `academic_helplessness`.
  - If the student is fearful of the upcoming evaluation itself, tag `exam_anxiety`.

### 2.2 Class 2: `conceptual_confusion`
* **Definition:** Cognitive perplexity, epistemic breakdown, or difficulty understanding subject matter, theory, algorithms, equations, or instructional material.
* **Core Emotional Tone:** Uncertainty, perplexity, cognitive overload, bewilderment.
* **Linguistic Indicators:** "I've re-read slide 14 five times and still don't get how X leads to Y", "totally lost on dynamic programming memoization", "the textbook and lecture notes contradict each other", "can someone explain why the derivative turns negative here?".
* **Boundary Rules:**
  - Must be focused on the academic *content* or learning material itself.
  - If the confusion is about *where to submit* or *due date ambiguity*, tag `course_frustration`.
  - If cognitive perplexity leads to despair ("I'm too dumb to get this"), tag BOTH `conceptual_confusion` and `academic_helplessness`.

### 2.3 Class 3: `academic_helplessness`
* **Definition:** Affective resignation, perceived lack of agency, hopelessness, or the belief that no amount of personal effort will lead to academic success.
* **Core Emotional Tone:** Sadness, despair, defeatism, self-blame, hopelessness.
* **Linguistic Indicators:** "no matter how much I study, nothing works", "I give up, there's no point in trying anymore", "I'm just not cut out for computer science", "I feel completely hopeless in this course", "what's the point of submitting when I'm guaranteed to fail?".
* **Boundary Rules:**
  - Marked by an internal attribution of failure and absence of perceived solutions.
  - Differs from `motivation_erosion`: Helplessness is rooted in *despair and powerlessness*; motivation erosion is rooted in *apathy and burnout*.

### 2.4 Class 4: `course_frustration`
* **Definition:** Irritation, anger, or resentment aimed at institutional, operational, or instructional friction—such as broken LMS portals, vague assignment specs, delayed grading, unresponsive teaching staff, or conflicting instructions.
* **Core Emotional Tone:** Annoyance, anger, exasperation, resentment.
* **Linguistic Indicators:** "the grading rubric makes zero sense", "the autograder has been down for 48 hours before the deadline", "the professor ignored three emails this week", "why are we being tested on material that was never covered in lectures?".
* **Boundary Rules:**
  - Directed at *external course friction* rather than internal inability.
  - If angry about confusing course theory, differentiate whether the frustration is primarily pedagogical/operational (`course_frustration`) or epistemic/conceptual (`conceptual_confusion`). Both can be assigned if present.

### 2.5 Class 5: `motivation_erosion`
* **Definition:** Progressive disengagement, psychological burnout, apathy, loss of academic curiosity, chronic procrastination, or emotional numbness toward coursework.
* **Core Emotional Tone:** Apathy, boredom, exhaustion, chronic disengagement.
* **Linguistic Indicators:** "I can't bring myself to open the course portal anymore", "zero energy to attend lectures this week", "feeling completely burned out and detached", "I used to love this subject, now I just don't care at all", "dragging myself to complete the bare minimum".
* **Boundary Rules:**
  - Marked by flat affect or lack of motivation rather than acute panic or active despair.
  - If the student is expressing exhaustion without hopelessness, tag `motivation_erosion`. If accompanied by deep depressive resignation about their ability to pass, tag BOTH `motivation_erosion` and `academic_helplessness`.

---

## 3. Disambiguation Matrix & Edge Cases

| Scenario / Ambiguous Text | Primary Tag | Secondary Tag (if applicable) | Rationale |
|---|:---:|:---:|---|
| *"I've been staring at this recursion problem for 4 hours and I have no clue what base case to use."* | `conceptual_confusion` | — | Epistemic cognitive blockage on specific subject matter. |
| *"I've been staring at this problem for 4 hours, I can't do this, I'm going to drop out."* | `conceptual_confusion` | `academic_helplessness` | Cognitive confusion coupled with acute resignation/agency loss. |
| *"The LMS quiz locked me out with 10 minutes left and now I failed!"* | `course_frustration` | `exam_anxiety` | Friction with platform tool during assessment conditions. |
| *"Tomorrow's final exam is worth 60% and my hands are literally shaking."* | `exam_anxiety` | — | Classic anticipatory assessment panic. |
| *"I haven't submitted the last two labs. I just don't see any value in this course anymore."* | `motivation_erosion` | — | Disengagement and apathy regarding academic utility. |
| *"Where can I find the Zoom link for Thursday's office hours?"* | `"none"` | — | Purely logistical / informational query without negative affect. |

---

## 4. Annotation Workflow & Agreement Protocol

1. **Independent Dual Annotation:** Each batch of student texts must be annotated independently by at least two trained annotators without cross-communication.
2. **Confidence Scoring:** For each assigned label, annotators assign a confidence rating from 1 to 5:
   - `5`: Unambiguous, explicit textual evidence.
   - `4`: Clear implication with standard vocabulary.
   - `3`: Moderate inference required from context.
   - `2`: Weak or ambiguous cue.
   - `1`: Speculative guess (should generally default to `"none"`).
3. **Inter-Annotator Agreement Target:**
   - Evaluated using **Cohen's Kappa ($\kappa$)** for pairwise agreement or **Krippendorff's Alpha ($\alpha$)** for multi-annotator datasets.
   - **Quality Threshold:** $\kappa \ge 0.70$ across all distress categories.
   - If $\kappa < 0.65$ on any category, a calibration meeting is mandatory before proceeding.
4. **Adjudication:** Cases where annotators disagree or where confidence $\le 2$ must be reviewed by the Lead ML Researcher / C1 Owner (Nidu) for final resolution.

---

## 5. Data Template Format

Annotators must record their decisions in CSV files matching this schema:

| Column Name | Data Type | Description |
|---|---|---|
| `text` | string | Normalized student utterance or message. |
| `label` | string | Single primary label or comma-separated list of distress classes (or `"none"`). |
| `annotator` | string | Unique identifier of the human annotator (e.g., `annotator_1`). |
| `confidence` | integer | Confidence rating from 1 (low) to 5 (high). |
| `notes` | string | Brief rationale or identified keywords/tokens. |
| `source` | string | Set to `domain` (real student LMS data) or `synthetic`. |
| `reviewed` | boolean | Set to `true` once verified by human annotator; otherwise `false`. |

> [!CAUTION]
> **Data Partitioning Rule:** Domain data gathered through this annotation guide must NEVER be added to `test_proxy.csv`. Real domain data is partitioned strictly into `domain_train.csv` and `domain_val.csv` (or retained for future human-written `test_real.csv`).
