# Emotion-Aware Student Early Warning System

<p align="center">
  <strong>AI-Driven Early Warning System for Student Disengagement, Stress, and Dropout Risk in Higher Education</strong>
</p>

<p align="center">
  An AI-powered, multimodal and longitudinal learning analytics system designed to identify emerging student dropout risk and recommend appropriate early interventions.
</p>

---

## 📌 Overview

Student dropout is a significant challenge in higher education. Traditional early-warning approaches often rely on static indicators such as grades, attendance, or LMS activity. Although these indicators can identify students who are already struggling, they may fail to capture the gradual development of disengagement, academic stress, and emotional difficulties.

The **Emotion-Aware Student Early Warning System** aims to address this limitation by combining multiple dimensions of student learning data:

- 🧠 Emotional and affective indicators
- 📊 Longitudinal engagement behavior
- 🎓 Academic performance
- 📝 Assessment and submission behavior
- 🕒 Temporal learning patterns
- 🤝 Personalized intervention recommendations

Rather than simply answering:

> **"Which students are at risk?"**

the system aims to answer:

> **"Which students are becoming at risk, why might they be at risk, and what intervention could help?"**

---

# 🎯 Research Objective

The primary objective of this research is:

> **To develop and evaluate a proactive AI-driven early warning system that combines student emotional states, longitudinal engagement patterns, and academic performance to predict dropout risk and recommend cause-matched interventions.**

---

# 🔬 Research Components

The research consists of four interconnected components.

## 1. 🧠 Student Affective State Detection

This component analyzes student-generated textual data to identify academic-related emotional and affective states.

### Potential Inputs

- Student reflections
- Discussion forum posts
- Chat messages
- Learning journals
- Feedback responses

### Potential Outputs

- Stress
- Frustration
- Anxiety
- Motivation
- Confusion
- Disengagement-related indicators

### Research Focus

Generic sentiment analysis may not accurately capture academic stress or learning-related emotions.

Therefore, this component investigates domain-adapted emotion classification for educational contexts.

### Pipeline

```text
Student Text
     ↓
Text Preprocessing
     ↓
Feature Extraction
     ↓
Emotion Classification
     ↓
Affective State Scores