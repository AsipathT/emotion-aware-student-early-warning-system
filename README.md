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

## 🚀 Features

The system acts as an LMS with integrated analytics capabilities.
Key features developed in the current iteration include:

- **Authentication & RBAC**: Fully functional authentication system with roles (student, lecturer, admin).
- **Course & Content Management**: Robust models for tracking enrollments, assignments, quizzes, and module progression.
- **Behavioral & Interaction Tracking**: Automatically tracks `UserSession` and click events throughout the LMS to generate longitudinal behavioral metrics.
- **Weekly Analytics Aggregation Job**: A scheduled background job computes rich weekly features (e.g., session frequency, active days, video interaction intensity) for every enrolled student.
- **Affective State Ingestion**: Endpoints allowing admins to bulk-ingest emotion and affect scores extracted from student communication.
- **Longitudinal Risk Trajectories**: Tracking and visualization of week-by-week multimodal stress vs. engagement data using a dynamic `Recharts`-based dashboard.
- **Synthetic Data Generator**: Capable of generating robust datasets with synthetic engagement and affective profiles to test the machine learning pipeline.
- **Analytics Exporter**: One-click download of the `training_data.csv` which perfectly aligns academic, affective, and behavioral modalities for model training.

---

## ⚙️ Technology Stack

**Backend:**
- Python 3.10+
- FastAPI (High performance async framework)
- SQLAlchemy 2.0 (Async DB access)
- PostgreSQL (Primary Datastore)
- APScheduler (For background weekly aggregation)
- Alembic (Database migrations)

**Frontend:**
- React 18 & TypeScript
- Vite (Fast development tooling)
- TailwindCSS (Utility-first styling)
- TanStack Query (Data fetching, caching)
- Recharts (Data visualization & plotting)

---

## 🔧 Running Locally

**1. Database and Backend:**
Using Docker Compose:
```bash
docker-compose up -d
```
(This provisions the Postgres database and runs the FastAPI server at `http://localhost:8000`)

**2. Database Migrations:**
Ensure the models are applied:
```bash
docker exec -i lms_backend alembic upgrade head
```

**3. Frontend Dev Server:**
```bash
cd frontend
npm install
npm run dev
```
(The Vite frontend is available at `http://localhost:5173`)

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
```