# C4 Adaptive Intervention Recommendation

This folder holds the model work and a web app that uses the trained model.

| Folder / file | What it is |
|---|---|
| `C4_Suitable_Intervention_Model.ipynb` | Colab notebook that trains and tests the model |
| `C4_ML_Training_Dataset_500_IT23_v2.xlsx` | Training data (labels follow the rules listed in its README sheet) |
| `make_training_data_v2.py` | Recreates the v2 training data from the original file |
| `backend/` | Python API (FastAPI): login, model predictions, history, AI explanations |
| `frontend/` | React app (Vite) |

## How the app works

1. Sign in as the admin user.
2. **Students:** pick a student from the list.
3. **New assessment:** enter the model inputs: C1 condition, C2 trajectory, dropout risk score (sets the risk tier), and the C3 Affective / Behavioural / Academic values.
4. **Dashboard:** shows the student's inputs and the top recommendation with its suitability score (the model's probability).
5. **Recommendation details:** shows the top recommendation, the two other options from the model, and a short explanation written by OpenAI. The explanation is labelled as AI-generated. It also uses the student's past recommendations.
6. **Intervention History:** shows every past recommendation, with a filter by student.

All data is kept in JSON files in `backend/data/`; there is no database.

| File | Contents |
|---|---|
| `users.json` | Seeded admin user (hashed password) |
| `students.json` | Seeded demo students |
| `assessments.json` | Every assessment: inputs, top 3 recommendations, and the AI explanation once generated |

## Run it

You need Python 3.10+ and Node.js 18+.

### 1. Backend (port 8000)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Put your OpenAI key in `backend/.env` as `OPENAI_API_KEY=...`. Without a key, everything works except the AI explanation, which shows a "turned off" message.

### 2. Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with:

- **Username:** `admin`
- **Password:** `admin123`

Change the password before showing this to anyone outside the team. To do that, edit `ADMIN` in `backend/app/seed.py`, then reset the demo data (below).

## Useful commands (run in `backend/`)

| Command | What it does |
|---|---|
| `python -m app.seed --reset` | Resets users, students and history back to the seed data |
| `python train_model.py` | Retrains the model from `model/C4_ML_Training_Dataset_500_IT23_v2.xlsx` |
| `python train_model.py path\to\data.xlsx` | Retrains from another file with the same columns |

You can also use a model exported from the notebook (`c4_intervention_model.joblib`): copy it into `backend/model/`. If it was saved with a different scikit-learn version, the backend retrains it automatically at start-up.

## API (all under `/api`; everything except login needs `Authorization: Bearer <token>`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | Username + password → token |
| GET | `/auth/me` | Current user |
| GET | `/reference` | Allowed input values, descriptions, model and OpenAI status |
| GET | `/students` | Students with their latest recommendation |
| GET | `/students/{id}` | One student, latest assessment and history summary |
| POST | `/students/{id}/assessments` | Run the model on new inputs and save the result |
| GET | `/assessments?student_id=` | History, newest first |
| GET | `/assessments/{id}` | One assessment, the student, and earlier assessments |
| POST | `/assessments/{id}/explanation` | AI explanation (cached; send `{"refresh": true}` to regenerate) |

Interactive docs: http://localhost:8000/docs

## Notes

- **What is sent to OpenAI:** the model inputs, the model's top 3 and earlier recommendations. Names and student IDs are not sent.
- **The training data is synthetic.** Suitability scores show how well the inputs match the labelling rules in the dataset. They are not evidence of real-world effectiveness. The counsellor makes the final decision.
