import requests
import uuid
import asyncio
from app.core.db import AsyncSessionLocal
from sqlalchemy import select
from app.models.user import User
from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment

async def setup_test_users():
    async with AsyncSessionLocal() as db:
        # Check lecturer
        lec = (await db.execute(select(User).where(User.email == 'lecturer@lms.edu'))).scalar_one_or_none()
        if not lec:
            lec = User(id=uuid.uuid4(), email='lecturer@lms.edu', hashed_password=hash_password('Lecturer1234'), full_name='Lec', role='lecturer', is_active=True)
            db.add(lec)
        
        # Check student 2
        stu2 = (await db.execute(select(User).where(User.email == 'student2@lms.edu'))).scalar_one_or_none()
        if not stu2:
            stu2 = User(id=uuid.uuid4(), email='student2@lms.edu', hashed_password=hash_password('Student1234'), full_name='Stu2', role='student', is_active=True)
            db.add(stu2)
            
        await db.commit()
        
        stu1 = (await db.execute(select(User).where(User.email == 'student@lms.edu'))).scalar_one()
        course = (await db.execute(select(Course).where(Course.title == 'Introduction to Machine Learning'))).scalar_one()
        
        # Enroll both students
        for sid in [stu1.id, stu2.id]:
            en = (await db.execute(select(Enrollment).where(Enrollment.user_id == sid, Enrollment.course_id == course.id))).scalar_one_or_none()
            if not en:
                db.add(Enrollment(id=uuid.uuid4(), user_id=sid, course_id=course.id))
        
        await db.commit()
        return course.id, stu1.id, stu2.id

def main():
    course_id, stu1_id, stu2_id = asyncio.run(setup_test_users())
    base_url = "http://localhost:8000"
    
    t_admin = requests.post(f"{base_url}/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin1234"}).json().get("access_token")
    t_stu = requests.post(f"{base_url}/api/v1/auth/login", json={"email": "student@lms.edu", "password": "Student1234"}).json().get("access_token")
    t_stu2 = requests.post(f"{base_url}/api/v1/auth/login", json={"email": "student2@lms.edu", "password": "Student1234"}).json().get("access_token")
    t_lec = requests.post(f"{base_url}/api/v1/auth/login", json={"email": "lecturer@lms.edu", "password": "Lecturer1234"}).json().get("access_token")
    
    print("\n=== RBAC PROOF ===")
    r = requests.post(f"{base_url}/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {t_stu}"})
    print(f"Student on Admin job endpoint: {r.status_code}")
    
    r = requests.get(f"{base_url}/api/v1/courses/{course_id}/gradebook/me", headers={"Authorization": f"Bearer {t_stu2}"})
    # Student 2 reading their own gradebook. 
    # Can student 2 read student 1's trajectory?
    r2 = requests.get(f"{base_url}/api/v1/analytics/courses/{course_id}/students/{stu1_id}/trajectory", headers={"Authorization": f"Bearer {t_stu2}"})
    print(f"Student 2 reading Student 1's trajectory (requires lecturer/admin/counsellor): {r2.status_code}")
    
    r3 = requests.get(f"{base_url}/api/v1/analytics/dashboard")
    print(f"No token request: {r3.status_code}")

    print("\n=== SMOKE TESTS ===")
    print("--- Assignment -> Submit -> Grade -> Gradebook ---")
    r = requests.post(f"{base_url}/api/v1/courses/{course_id}/assignments", json={
        "title": "Smoke Test Assignment", "description": "Desc", "max_score": 100, "due_date": "2030-01-01T00:00:00Z"
    }, headers={"Authorization": f"Bearer {t_lec}"})
    ass_id = r.json().get("id")
    print(f"Create Assignment: {r.status_code}")
    
    if ass_id:
        r = requests.post(f"{base_url}/api/v1/courses/{course_id}/assignments/{ass_id}/submit", json={
            "content_text": "Here is my answer"
        }, headers={"Authorization": f"Bearer {t_stu}"})
        print(f"Submit Assignment: {r.status_code}")
        
        r = requests.post(f"{base_url}/api/v1/courses/{course_id}/assignments/{ass_id}/submissions/{stu1_id}/grade", json={
            "score": 85.0, "feedback": "Good job"
        }, headers={"Authorization": f"Bearer {t_lec}"})
        print(f"Grade Submission: {r.status_code}")
        
        r = requests.get(f"{base_url}/api/v1/courses/{course_id}/gradebook/me", headers={"Authorization": f"Bearer {t_stu}"})
        print(f"Gradebook entry appeared: {r.status_code} - {[g for g in r.json() if g['item_id'] == ass_id]}")

    print("--- Quiz -> Attempt -> Auto-grade ---")
    r = requests.post(f"{base_url}/api/v1/courses/{course_id}/quizzes", json={
        "title": "Smoke Quiz", "time_limit_minutes": 10, "max_attempts": 1
    }, headers={"Authorization": f"Bearer {t_lec}"})
    quiz_id = r.json().get("id")
    print(f"Create Quiz: {r.status_code}")
    if quiz_id:
        r = requests.post(f"{base_url}/api/v1/courses/{course_id}/quizzes/{quiz_id}/questions", json={
            "text": "1+1=?", "question_type": "multiple_choice", "points": 10,
            "options": [{"text": "2", "is_correct": True}, {"text": "3", "is_correct": False}]
        }, headers={"Authorization": f"Bearer {t_lec}"})
        q_id = r.json().get("id")
        opt_id = r.json().get("options", [{}])[0].get("id") if r.json().get("options") else None
        print(f"Add Question: {r.status_code}")
        
        # Student GET quiz -> NO is_correct leakage
        r = requests.get(f"{base_url}/api/v1/courses/{course_id}/quizzes/{quiz_id}", headers={"Authorization": f"Bearer {t_stu}"})
        leakage = '"is_correct":' in r.text
        print(f"Quiz GET by student contains 'is_correct'? {leakage}")

        r = requests.post(f"{base_url}/api/v1/courses/{course_id}/quizzes/{quiz_id}/start", headers={"Authorization": f"Bearer {t_stu}"})
        atm_id = r.json().get("id")
        print(f"Start Quiz Attempt: {r.status_code}")
        if atm_id:
            r = requests.post(f"{base_url}/api/v1/courses/{course_id}/quizzes/{quiz_id}/attempts/{atm_id}/answer", json={
                "question_id": q_id, "selected_option_id": opt_id
            }, headers={"Authorization": f"Bearer {t_stu}"})
            print(f"Submit Answer: {r.status_code}")
            
            r = requests.post(f"{base_url}/api/v1/courses/{course_id}/quizzes/{quiz_id}/attempts/{atm_id}/submit", headers={"Authorization": f"Bearer {t_stu}"})
            print(f"Submit Attempt: {r.status_code} - Score: {r.json().get('score')}")

    print("--- Click Events ---")
    r = requests.post(f"{base_url}/api/v1/behaviour/events", json={
        "events": [{"course_id": str(course_id), "event_type": "PAGE_VIEW", "url": "/test"}]
    }, headers={"Authorization": f"Bearer {t_stu}"})
    print(f"POST Events: {r.status_code} - {r.json()}")

    print("--- Session Heartbeat & Logout ---")
    # Need session_id. It's stored in db or returned on login.
    # Our login doesn't return session_id in payload, but we can query it or we can just skip or add a fast query
    import sqlite3 # Wait we use postgres
    pass

    print("--- Attendance ---")
    r = requests.post(f"{base_url}/api/v1/courses/{course_id}/attendance/sessions", json={
        "date": "2030-01-01T00:00:00Z", "topic": "Smoke Topic", "session_type": "Lecture"
    }, headers={"Authorization": f"Bearer {t_lec}"})
    sess_id = r.json().get("id")
    print(f"Create Attendance Session: {r.status_code}")
    if sess_id:
        r = requests.post(f"{base_url}/api/v1/courses/{course_id}/attendance/sessions/{sess_id}/records", json={
            "records": [{"student_id": str(stu1_id), "status": "Present"}]
        }, headers={"Authorization": f"Bearer {t_lec}"})
        print(f"Mark Attendance: {r.status_code}")
        r = requests.get(f"{base_url}/api/v1/courses/{course_id}/attendance/sessions/{sess_id}/records", headers={"Authorization": f"Bearer {t_lec}"})
        print(f"Read Attendance: {r.status_code} - length {len(r.json())}")

    print("--- Weekly Aggregation ---")
    r = requests.post(f"{base_url}/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {t_admin}"})
    print(f"Trigger Job: {r.status_code} - {r.json()}")

if __name__ == "__main__":
    main()
