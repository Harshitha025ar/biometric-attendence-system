import os
import mysql.connector

# Backend base folder
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_DIR = os.path.join(BACKEND_DIR, "dataset")
MODEL_DIR = os.path.join(BACKEND_DIR, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "lbph_model.yml")

# Create directories if missing
os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# Attendance timing
ATTENDANCE_START_TIME = "09:00"   # ON_TIME <= 9:00
ATTENDANCE_CUTOFF_TIME = "23:00"  # after 9:15 attendance stops

def get_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="Varsharaghu@08",
        database="faculty_biometric"
    )
