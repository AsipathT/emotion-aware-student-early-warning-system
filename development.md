# LMS Technology Stack & Architecture (Project J26-IT-349)

## 1. Technology Stack
* **Backend:** Python 3.11+, FastAPI + Uvicorn
* **Data Validation:** Pydantic v2
* **Database:** PostgreSQL 15/16 (Single shared database, no MongoDB)
* **ORM/Migrations:** SQLAlchemy 2.0 + Alembic
* **Authentication:** JWT (access + refresh), bcrypt (Roles: Student, Lecturer, Counsellor, Admin)
* **Scheduled Jobs:** APScheduler
* **Frontend:** React 18+ TypeScript + Vite, Tailwind CSS, React Router, TanStack Query, Axios, Recharts
* **Containers:** Docker + Docker Compose
* **API Prefix:** All routes must be versioned under `/api/v1/`
* **Timezones:** UTC timestamps everywhere

## 2. Monorepo Structure
lms/
├── backend/
│   ├── app/
│   │   ├── core/ (config, security, db session)
│   │   ├── models/ (SQLAlchemy models)
│   │   ├── schemas/ (Pydantic schemas)
│   │   ├── routers/ (One file per feature area)
│   │   ├── services/ (Business logic)
│   │   └── jobs/ (Scheduled jobs)
│   └── alembic/
└── frontend/
    └── src/

## 3. Member 1 Responsibilities (Platform Foundation)
I am Member 1. My assigned features are:
* 1: Authentication and role-based access
* 2: User and student profile management
* 3: Course and module management
* 4: Enrolment management
* 5: Pseudonymization and anonymization layer
* 6: Consent and ethics notice
* 7: Audit log
* 21: Data export/ API for components
* 22: Weekly scheduler / trigger
* 23: Ingestion endpoints for component outputs
* 24: Shared JSON schema and versioning
* 25: Central PostgreSQL schema
* 26: OULAD import tool
* 40: Admin panel