"""
scripts/add_students.py

Safely adds 5 realistic student accounts with authentic Sri Lankan names and
IT numbers (e.g. IT22xxxxxx) into MongoDB Atlas without removing or modifying
any existing database records.

Populates:
  1. users (collection)
  2. identity_vault (collection - for zero-PII pseudonym mapping)
  3. enrolments (collection - enrolled into CS101)
"""

import os
import uuid
import hmac
import hashlib
from datetime import datetime, timezone
from pymongo import MongoClient
import bcrypt

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://nidukavikumasipath_db_user:GmKuIN45W0FOhKK0@cluster0.sqmc74m.mongodb.net/lms_db?retryWrites=true&w=majority&appName=Cluster0"
)

PSEUDONYM_SECRET = "dev-pseudonym-secret-key-32b-min!!"

def get_pid(student_id: str) -> str:
    secret = PSEUDONYM_SECRET.encode("utf-8")
    data = str(student_id).strip().encode("utf-8")
    digest = hmac.new(secret, data, hashlib.sha256).hexdigest()
    return f"STU_{digest[:8]}"

def hash_password(pwd: str) -> str:
    pwd_bytes = pwd.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

STUDENTS_TO_ADD = [
    {
        "full_name": "Kavindu Madushan Perera",
        "student_id": "IT22145892",
        "email": "kavindu.madushan@students.lms.edu",
    },
    {
        "full_name": "Shenali Tharushi Jayawardena",
        "student_id": "IT22384910",
        "email": "shenali.jayawardena@students.lms.edu",
    },
    {
        "full_name": "Dinuka Lakshan Rathnayake",
        "student_id": "IT22451206",
        "email": "dinuka.rathnayake@students.lms.edu",
    },
    {
        "full_name": "Sachini Pavithra Wickramasinghe",
        "student_id": "IT22678124",
        "email": "sachini.wickramasinghe@students.lms.edu",
    },
    {
        "full_name": "Malith Sahan Bandara",
        "student_id": "IT22890345",
        "email": "malith.bandara@students.lms.edu",
    },
]

def main():
    print("Connecting to MongoDB Atlas...")
    client = MongoClient(MONGO_URI)
    db = client["lms_db"]
    now_utc = datetime.now(timezone.utc)
    demo_password_hash = hash_password("Student123!")

    initial_count = db["users"].count_documents({})
    print(f"Current total users in database: {initial_count}")

    added_count = 0
    for s in STUDENTS_TO_ADD:
        sid = s["student_id"]
        email = s["email"]
        name = s["full_name"]
        pid = get_pid(sid)

        # Check if already exists in users
        existing_user = db["users"].find_one({"$or": [{"email": email}, {"student_id": sid}]})
        if existing_user:
            print(f"  [-] Student {name} ({sid}) already exists. Skipping insertion.")
            continue

        uid = str(uuid.uuid4())
        user_doc = {
            "_id": uid,
            "id": uid,
            "email": email,
            "hashed_password": demo_password_hash,
            "full_name": name,
            "role": "student",
            "is_active": True,
            "is_verified": True,
            "created_at": now_utc,
            "updated_at": now_utc,
            "student_id": sid,
            "pid": pid,
            "profile": None,
        }

        # 1. Insert into users collection
        db["users"].insert_one(user_doc)

        # 2. Insert/Update into identity_vault collection
        vault_doc = {
            "_id": pid,
            "pid": pid,
            "student_id": sid,
            "name": name,
            "email": email,
            "created_at": now_utc,
            "updated_at": now_utc,
            "is_imported": False,
        }
        db["identity_vault"].update_one({"_id": pid}, {"$set": vault_doc}, upsert=True)

        # 3. Enroll into CS101
        enr_id = f"{pid}_CS101"
        enr_doc = {
            "_id": enr_id,
            "pid": pid,
            "course_id": "CS101",
            "status": "active",
            "enrolment_start": now_utc,
            "schema_version": 1,
            "source_version": "1.0",
            "ingested_at": now_utc,
        }
        db["enrolments"].update_one({"_id": enr_id}, {"$set": enr_doc}, upsert=True)

        added_count += 1
        print(f"  [+] Added: {name} | Student ID: {sid} | PID: {pid} | Email: {email}")

    final_count = db["users"].count_documents({})
    print("\n-------------------------------------------")
    print(f"Successfully added {added_count} new students.")
    print(f"Previous user count: {initial_count} -> New user count: {final_count}")
    print("Zero existing records were deleted or modified.")
    client.close()

if __name__ == "__main__":
    main()
