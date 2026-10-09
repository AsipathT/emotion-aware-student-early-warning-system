import requests
import uuid
from app.core.pseudonym import pseudonymize
from app.core.db import AsyncSessionLocal
import asyncio
from sqlalchemy import select
from app.models.user import User
from app.models.course import Course

async def get_test_data():
    async with AsyncSessionLocal() as db:
        student = (await db.execute(select(User).where(User.email == 'student@lms.edu'))).scalar_one()
        course = (await db.execute(select(Course).where(Course.title == 'Introduction to Machine Learning'))).scalar_one()
        return student.id, course.id

def main():
    base_url = "http://localhost:8000"
    
    # 1. Login Admin
    r = requests.post(f"{base_url}/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin1234"})
    admin_token = r.json()["access_token"]
    
    # 2. Login Student
    r = requests.post(f"{base_url}/api/v1/auth/login", json={"email": "student@lms.edu", "password": "Student1234"})
    student_token = r.json()["access_token"]
    
    print("\n--- 4. POST /api/v1/jobs/aggregate-weekly ---")
    r = requests.post(f"{base_url}/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {student_token}"})
    print("Student response:", r.status_code, r.text)
    
    r = requests.post(f"{base_url}/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {admin_token}"})
    print("Admin response:", r.status_code, r.text)

    # 3. Test Ingestion Endpoints
    print("\n--- 2 & 3. Ingestion & Pseudonymisation ---")
    student_id, course_id = asyncio.run(get_test_data())
    pseudo_id = pseudonymize(str(student_id))
    print(f"Real ID: {student_id} -> Pseudo ID: {pseudo_id}")
    
    affect_payload = {
        "records": [{
            "pseudo_student_id": pseudo_id,
            "course_id": str(course_id),
            "week_index": 1,
            "exam_anxiety": 0.5,
            "conceptual_confusion": 0.3,
            "message_count": 5
        }]
    }
    r = requests.post(f"{base_url}/api/v1/affect/ingest", json=affect_payload, headers={"Authorization": f"Bearer {admin_token}"})
    print("Affect Ingest:", r.status_code, r.text)
    
    print("\n--- Endpoints Empty States ---")
    r = requests.get(f"{base_url}/api/v1/analytics/courses/{course_id}/cohort", headers={"Authorization": f"Bearer {admin_token}"})
    print("Cohort empty:", r.status_code, r.text)
    
    r = requests.get(f"{base_url}/api/v1/analytics/courses/{course_id}/students/{student_id}/risk-detail", headers={"Authorization": f"Bearer {admin_token}"})
    print("Risk detail empty:", r.status_code, r.text)
    
if __name__ == "__main__":
    main()
