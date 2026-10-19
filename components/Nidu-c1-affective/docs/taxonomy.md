# Academic Distress Taxonomy & Annotation Guide

**Component 1 (C1): Student Affective State Detection**  
*Project J26-IT-349: AI-Driven Early Warning System for Student Dropout in Higher Education (SLIIT)*  
*Owner: Nidu*  
*Version: 1.0.0 (October 2026)*  
*Authoritative Schema Reference: `contracts/v1/AffectiveWeeklyVector.json`*

---

## 1. Theoretical Grounding

This taxonomy adapts Pekrun's **Control-Value Theory of Achievement Emotions** to the context of online learning platforms (LMS). Academic emotions are categorized along three dimensions:
- **Valence** (positive vs. negative)
- **Arousal / Activation** (activating vs. deactivating)
- **Object Focus** (outcome, activity, or social/institutional context)

While general NLP benchmarks classify universal emotions (e.g., Ekman's 6 basic emotions or Plutchik's wheel), higher education early-warning systems require actionable indicators of academic attrition risk. The C1 taxonomy comprises **5 fine-grained distress classes** directly tied to cognitive struggle, emotional crises, and withdrawal behaviors.

---

## 2. The 5 Academic Distress Classes

### 2.1 `exam_anxiety`
- **Theoretical Type:** Negative, activating, outcome-focused emotion.
- **Definition:** Anticipatory apprehension, physiological dread, catastrophic rumination, or acute worry centered around upcoming evaluative milestones (midterms, final exams, assignment deadlines, or defense presentations).
- **Core Indicators:**
  - Mentions of panic, racing thoughts, sleep disruption before deadlines.
  - Fear of failing or grade point average collapse.
  - Urgent requests for extensions fueled by distress.
- **Realistic Student Examples:**
  1. *"I have the database midterm tomorrow and I'm having a complete panic attack, my mind goes blank every time I look at SQL joins."*
  2. *"I'm terrified I'm going to fail this exam and lose my scholarship, I haven't slept for two days."*
  3. *"The countdown timer on the quiz gave me such bad test anxiety that my hands were shaking and I couldn't finish."*
  4. *"Is there any possibility of an extension? I'm overwhelmed and terrified of turning in incomplete work."*
- **Key Lexical Markers:** `panic`, `terrified`, `shaking`, `blank out`, `fear of failing`, `deadline dread`, `anxious`, `freaking out`, `stressing over exam`.

---

### 2.2 `conceptual_confusion`
- **Theoretical Type:** Epistemic negative activating emotion (cognitive disequilibrium).
- **Definition:** Perplexity, bewilderment, and cognitive impasse resulting from a breakdown in comprehension of instructional concepts, lecture slides, algorithmic logic, or assignment requirements.
- **Core Indicators:**
  - Explicit statements of misunderstanding technical content.
  - Repeated failed attempts to grasp an abstract concept.
  - Contradiction between student's mental model and lecture outcomes.
- **Realistic Student Examples:**
  1. *"I've watched the lecture on dynamic programming three times and I still don't understand how the memoization table updates."*
  2. *"Can someone explain the difference between processes and threads in simple terms? The textbook explanation makes zero sense to me."*
  3. *"I'm completely lost on step 4 of the lab guide—are we supposed to instantiate the object before or after configuring the environment?"*
  4. *"I thought I understood normal forms, but 3NF versus BCNF is confusing me completely on question 2."*
- **Key Lexical Markers:** `confused`, `don't understand`, `makes no sense`, `lost`, `can't wrap my head around`, `clarify`, `stuck on concept`, `perplexed`.

---

### 2.3 `academic_helplessness`
- **Theoretical Type:** Negative, deactivating, low perceived-control outcome emotion.
- **Definition:** Learned helplessness, subjective defeatism, and perceived futility. The student feels that no matter how much effort they invest, academic failure is inevitable, reflecting a catastrophic collapse in academic self-efficacy.
- **Core Indicators:**
  - Resignation, despair, and expressions of intrinsic inadequacy ("I'm not smart enough for CS").
  - Feeling completely abandoned or unable to salvage the semester.
  - Strongest text-based leading indicator of imminent course withdrawal or dropout.
- **Realistic Student Examples:**
  1. *"There is literally no point in studying anymore. I'm just not cut out for computer science and I'm going to fail regardless."*
  2. *"I've tried everything for this module, spent 20 hours on the project, and failed the auto-grader anyway. I give up, nothing I do works."*
  3. *"I'm hopelessly behind on all coursework. It's impossible to catch up at this stage, I just feel defeated."*
  4. *"I feel so stupid compared to everyone else in this forum. No matter how hard I try, I will never pass this course."*
- **Key Lexical Markers:** `no point`, `give up`, `impossible to catch up`, `not cut out for`, `hopeless`, `defeated`, `nothing works`, `failing regardless`, `waste of time`.

---

### 2.4 `course_frustration`
- **Theoretical Type:** Negative, activating, context/activity-focused emotion.
- **Definition:** Anger, exasperation, irritation, or resentment provoked by external institutional or pedagogical barriers—such as ambiguous rubrics, broken autograders, unhelpful instructor feedback, server crashes, or dysfunctional group members.
- **Core Indicators:**
  - Attribution of difficulty to external course structures rather than internal ability.
  - Complaining about unannounced schedule shifts or disorganized learning materials.
  - High emotional arousal directed towards the platform or staff.
- **Realistic Student Examples:**
  1. *"The autograder has been down for 6 hours before the deadline and nobody on the teaching team is responding! This is ridiculous."*
  2. *"The assignment rubric contradicts what was said in the lecture. How are we expected to complete this when the requirements keep changing?"*
  3. *"My group members haven't submitted a single line of code and the submission is tonight. Why am I being forced to carry this entire project?"*
  4. *"The exam questions were completely unfair and had nothing to do with what was covered in the syllabus."*
- **Key Lexical Markers:** `unfair`, `ridiculous`, `autograder broken`, `waste of money`, `contradictory`, `nobody replies`, `angry`, `annoyed`, `rubric makes no sense`.

---

### 2.5 `motivation_erosion`
- **Theoretical Type:** Negative, deactivating, value-depleted emotion.
- **Definition:** Chronic apathy, alienation, boredom, loss of intrinsic and extrinsic drive, and emotional withdrawal from the learning community. The student disinvests attention and stops caring about grades or course goals.
- **Core Indicators:**
  - Passive disengagement, cynicism regarding the degree or curriculum.
  - Expressing indifference to late penalties or missing submissions.
  - Shift from active frustration to numb detachment.
- **Realistic Student Examples:**
  1. *"Honestly, I just can't bring myself to care about this module anymore. Whether I pass or fail doesn't even bother me now."*
  2. *"I haven't opened the lecture slides in two weeks. I just completely lost all interest in this degree."*
  3. *"Skipping today's quiz. I don't have the energy or motivation to sit through another meaningless assignment."*
  4. *"Everything in this course feels so tedious and pointless. I'm just going through the motions until the semester ends."*
- **Key Lexical Markers:** `don't care anymore`, `lost interest`, `going through the motions`, `no motivation`, `apathetic`, `skipping`, `can't bring myself to`, `meaningless`.

---

## 3. Disambiguation & Edge-Case Rules

| Case | Dilemma | Resolution Rule |
|---|---|---|
| **A** | `conceptual_confusion` vs. `course_frustration` | **Locus of Cause:** If the student attributes difficulty to their understanding of the topic ("I can't grasp pointers"), label `conceptual_confusion`. If they attribute it to deficient instruction or ambiguous rubrics ("The slides on pointers are incomprehensible and poorly written"), label `course_frustration`. |
| **B** | `exam_anxiety` vs. `academic_helplessness` | **Temporal & Agency Focus:** `exam_anxiety` is forward-looking and activating ("I'm terrified about tomorrow's exam, I must cram"). `academic_helplessness` is past/present surrender and deactivating ("I failed the quiz and I give up, there's no point in cramming"). |
| **C** | `course_frustration` vs. `motivation_erosion` | **Arousal & Investment:** `course_frustration` features active emotional engagement and anger ("Fix this autograder!"). `motivation_erosion` features low arousal, disinterest, and apathy ("Whatever, I'm not submitting it"). |
| **D** | `academic_helplessness` vs. `motivation_erosion` | **Distress vs. Indifference:** `academic_helplessness` carries acute emotional despair and feeling inadequate ("I'm devastated, I can't do this"). `motivation_erosion` carries indifference and lack of value ("I just don't care about this subject"). |
| **E** | Compound statements (Multiple distress markers) | Apply the **Single-Label Tie-Breaking Priority Hierarchy** below. |

---

## 4. Single-Label Tie-Breaking Priority Hierarchy

When a single message exhibits traits across multiple distress categories, the annotator / single-label pipeline must resolve ties according to clinical/advising dropout risk urgency:

```
[1] academic_helplessness   (Highest Dropout Risk Signal: acute resignation)
       ↓
[2] exam_anxiety            (High-Arousal Crisis: immediate intervention needed)
       ↓
[3] motivation_erosion      (Creeping Attrition Risk: progressive detachment)
       ↓
[4] course_frustration      (Pedagogical Friction: requires operational remediation)
       ↓
[5] conceptual_confusion    (Remediable Learning Gap: normal pedagogical struggle)
```

- Messages expressing purely positive affect (`gratitude`, `pride`, `enthusiasm`) or factual inquiries (`"What room is the lecture in?"`) are assigned **No Distress** (`null` / unmapped).

---

## 5. External Corpora Proxy Mapping

> [!IMPORTANT]
> **Research Honesty Declaration:**
> The public pretraining datasets (GoEmotions from Reddit and Emotion-4 from Twitter) reflect broad social media sentiment and do **not** originate from real higher-education academic environments. All mappings from these datasets to our 5 academic distress classes are strictly **heuristic proxies**. They enable domain transfer learning, but cannot replace verified education-domain annotations.

### 5.1 GoEmotions (28 Labels) → C1 Taxonomy

| External Label | Mapped C1 Class | Type | Justification / Rationale |
|---|---|---|---|
| `nervousness` | `exam_anxiety` | **Proxy** | Direct indicator of physiological tension, acute apprehension, and nervousness. |
| `fear` | `exam_anxiety` | **Proxy** | Dread of negative outcomes, panic, and distress under evaluative pressure. |
| `confusion` | `conceptual_confusion` | **Proxy** | Explicit cognitive uncertainty, ambiguity, and perplexity. |
| `sadness` | `academic_helplessness` | **Proxy** | Low-control negative affect, sorrow, and demoralization. |
| `anger` | `course_frustration` | **Proxy** | High-arousal hostility and resentment toward external hurdles. |
| `annoyance` | `course_frustration` | **Proxy** | Irritation and exasperation with logistical friction and policies. |
| `disapproval` | `course_frustration` | **Proxy** | Critical dissatisfaction and dispute regarding course requirements. |
| `disappointment` | `motivation_erosion` | **Proxy** | Dashed expectations and disillusioned morale leading to disengagement. |
| `embarrassment` | `null` | **Ignore (Proxy)** | Excluded from training; interpersonal awkwardness does not cleanly map to academic motivation erosion. |
| `remorse` | `null` | **Ignore (Proxy)** | Excluded from training; personal guilt does not cleanly map to academic helplessness. |
| `grief` | `null` | **Ignore (Proxy)** | Excluded from training; personal bereavement is out of scope for LMS academic distress. |
| `disgust` | `null` | **Ignore (Proxy)** | Excluded from training; visceral revulsion introduces noise into course frustration. |
| *(16 remaining)* | `null` | **Unmapped** | Positive (`joy`, `admiration`, `gratitude`, `pride`, `relief`, `love`, `optimism`, `caring`, `desire`, `amusement`, `approval`), epistemic (`curiosity`, `realization`), or neutral (`neutral`, `surprise`). |

> **Ignore-Label Rule:** If a sample contains an ignore label alongside a mapped distress label (e.g., `disgust` + `anger`), it is **kept** with the distress label(s) as positives. Only samples whose labels are ignore-only or ignore plus unmapped are excluded from training, ensuring they are not used as noisy negatives.

### 5.2 Emotion-4 Dataset (`eng_dataset.csv`) → C1 Taxonomy

| External Label | Mapped C1 Class | Type | Justification / Rationale |
|---|---|---|---|
| `fear` | `exam_anxiety` | **Proxy** | Acute apprehension, dread, and evaluation terror. |
| `anger` | `course_frustration` | **Proxy** | High-arousal hostility, agitation, and friction. |
| `sadness` | `academic_helplessness` | **Proxy** | Demoralization, sorrow, and lack of perceived efficacy. |
| `joy` | `null` | **Unmapped** | Positive affect; non-distress baseline. |

---

## 6. Contract Conformance

All 5 taxonomy class names strictly match the `$defs.DistressClass` enum defined in `contracts/v1/AffectiveWeeklyVector.json`:
- `exam_anxiety`
- `conceptual_confusion`
- `academic_helplessness`
- `course_frustration`
- `motivation_erosion`
