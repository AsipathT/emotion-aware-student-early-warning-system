import requests

def main():
    base_url = "http://localhost:8000"
    
    # Admin login
    r = requests.post(f"{base_url}/api/v1/auth/login", json={"email": "admin@lms.edu", "password": "Admin1234"})
    if r.status_code != 200:
        print("Failed admin login:", r.text)
    else:
        admin_token = r.json()["access_token"]
        r = requests.post(f"{base_url}/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {admin_token}"})
        print("Admin /aggregate-weekly:", r.status_code, r.text)
        
    # Student login
    r = requests.post(f"{base_url}/api/v1/auth/login", json={"email": "student@lms.edu", "password": "Student1234"})
    if r.status_code == 200:
        student_token = r.json()["access_token"]
        r = requests.post(f"{base_url}/api/v1/jobs/aggregate-weekly", headers={"Authorization": f"Bearer {student_token}"})
        print("Student /aggregate-weekly:", r.status_code, r.text)
    else:
        print("Student login failed:", r.text)

if __name__ == "__main__":
    main()
