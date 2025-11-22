from flask import Flask, request, jsonify, render_template
import cv2
import numpy as np
from datetime import datetime, date, timedelta
import os

from config import (
    DATASET_DIR, MODEL_PATH, ATTENDANCE_START_TIME,
    ATTENDANCE_CUTOFF_TIME, get_db
)

from face_recognizer import FaceRecognizer

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static"
)

recognizer = FaceRecognizer()

# ---------------------------
# FRONTEND ROUTES
# ---------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register")
def reg_page():
    return render_template("register.html")

@app.route("/reports")
def reports_page():
    return render_template("reports.html")

# ---------------------------
# API: REGISTER FACULTY
# ---------------------------
@app.route("/api/faculty/register", methods=["POST"])
def api_register():
    data = request.form

    db = get_db()
    cur = db.cursor()

    cur.execute("""
        INSERT INTO faculty (faculty_code, name, department, email, phone)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        data["faculty_code"],
        data["name"],
        data["department"],
        data["email"],
        data["phone"]
    ))

    db.commit()
    return jsonify({"faculty_id": cur.lastrowid})

# ---------------------------
# API: UPLOAD TRAINING IMAGE
# ---------------------------
@app.route("/api/faculty/<int:fid>/upload_image", methods=["POST"])
def api_upload_image(fid):
    img = request.files.get("image")

    if img is None:
        return jsonify({"error": "No image received"}), 400

    # Read uploaded blob into OpenCV image (BGR)
    file_bytes = img.read()
    np_arr = np.frombuffer(file_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"error": "Invalid image"}), 400

    # ---- FACE DETECTION (Haar Cascade) ----
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80)
    )

    if len(faces) == 0:
        # No face found in this frame
        return jsonify({"error": "No face detected. Try again closer to the camera."}), 400

    # Take first detected face
    x, y, w, h = faces[0]

    # Crop and resize face region
    face_roi = gray[y:y + h, x:x + w]

    try:
        face_roi = cv2.resize(face_roi, (200, 200))
    except Exception as e:
        print("Resize error:", e)
        return jsonify({"error": "Error processing face image"}), 500

    # Save cropped face to dataset
    filename = f"{fid}_{datetime.now().timestamp()}.jpg"
    save_path = os.path.join(DATASET_DIR, filename)

    cv2.imwrite(save_path, face_roi)
    print(f"[DATASET] Saved cropped face: {save_path}")

    # Optional: also store path in face_images table (if you use it)
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO face_images (faculty_id, image_path)
            VALUES (%s, %s)
        """, (fid, filename))
        db.commit()
    except Exception as e:
        print("face_images insert error:", e)

    # Retrain LBPH model using new dataset
    recognizer.train_model()

    return jsonify({"status": "saved"})

# -----------------------------------------------------------
# API — REAL-TIME FACE RECOGNITION (WITH DUPLICATE FLAG)
# -----------------------------------------------------------
@app.route("/api/recognize", methods=["POST"])
def api_recognize():
    frame_file = request.files.get("frame")

    if frame_file is None:
        return jsonify({"detected": []})

    # Convert uploaded image to OpenCV format
    file_bytes = frame_file.read()
    np_arr = np.frombuffer(file_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    detections = recognizer.recognize_faces(frame)

    final_list = []
    db = get_db()
    cur = db.cursor(dictionary=True)

    for det in detections:
        fid = det["faculty_id"]

        # Get faculty info
        cur.execute("SELECT name, department FROM faculty WHERE id = %s", (fid,))
        info = cur.fetchone()
        if not info:
            continue

        # CHECK DUPLICATE
        cur.execute("""
            SELECT id FROM attendance
            WHERE faculty_id = %s AND date = %s
        """, (fid, date.today()))
        exists = cur.fetchone()

        duplicate_flag = exists is not None

        # INSERT ONLY IF NEW
        if not duplicate_flag:
            cur.execute("""
                INSERT INTO attendance 
                (faculty_id, faculty_name, faculty_department, date, arrival_time, status, late_by_minutes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                fid,
                info["name"],
                info["department"],
                date.today(),
                datetime.now().strftime("%H:%M:%S"),
                "Present",
                0
            ))
            db.commit()

        # SEND TO FRONTEND
        final_list.append({
            "faculty_id": fid,
            "name": info["name"],
            "department": info["department"],
            "confidence": det["confidence"],
            "duplicate": duplicate_flag   # IMPORTANT
        })

    return jsonify({"detected": final_list})

# -----------------------------------------------------------
# API — TODAY'S REPORT (FINAL, WITH DATE)
# -----------------------------------------------------------
@app.route("/api/reports/today")
def api_today_report():
    today = date.today()

    db = get_db()
    cur = db.cursor(dictionary=True)

    # 1) Get all faculty for absent list
    cur.execute("SELECT id, faculty_code, name, department FROM faculty ORDER BY id")
    all_faculty = cur.fetchall()

    # 2) TODAY'S attendance + include date column
    cur.execute("""
        SELECT 
            a.id AS attendance_id,
            a.faculty_id,
            a.faculty_name,
            a.faculty_department,
            a.date AS raw_date,
            a.arrival_time,
            a.status,
            a.late_by_minutes
        FROM attendance a
        WHERE a.date = %s
    """, (today,))
    present = cur.fetchall()

    print("RAW PRESENT ROWS:", present)  # for debugging

    # 3) Convert arrival_time (timedelta) + date to safe strings
    for p in present:

        # ---------- FORMAT DATE ----------
        d = p.get("raw_date")
        if isinstance(d, date):
            p["date"] = d.strftime("%Y-%m-%d")   # example: 2025-11-22
        else:
            p["date"] = str(d)

        # Remove raw_date after formatting
        p.pop("raw_date", None)

        # ---------- FORMAT ARRIVAL TIME ----------
        at = p.get("arrival_time")
        if isinstance(at, timedelta):
            total_seconds = int(at.total_seconds())
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            s = total_seconds % 60
            p["arrival_time"] = f"{h:02d}:{m:02d}:{s:02d}"
        else:
            p["arrival_time"] = str(at)

        # ---------- FORMAT LATE MINUTES ----------
        lb = p.get("late_by_minutes", 0)
        if isinstance(lb, timedelta):
            p["late_by_minutes"] = int(lb.total_seconds() // 60)
        else:
            try:
                p["late_by_minutes"] = int(lb)
            except:
                p["late_by_minutes"] = 0

    # 4) Build absent list
    present_ids = {row["faculty_id"] for row in present}
    absent = []

    for f in all_faculty:
        if f["id"] not in present_ids:
            absent.append({
                "faculty_id": f["id"],
                "faculty_code": f["faculty_code"],
                "name": f["name"],
                "department": f["department"]
            })

    # 5) Return clean JSON
    return jsonify({
        "present_count": len(present),
        "absent_count": len(absent),
        "present": present,
        "absent": absent
    })


# ---------------------------
# API: MONTHLY REPORT
# ---------------------------
@app.route("/api/reports/monthly")
def monthly_report():
    year = int(request.args.get("year", datetime.now().year))
    month = int(request.args.get("month", datetime.now().month))

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM faculty")
    faculty = cur.fetchall()

    cur.execute("""
        SELECT * FROM attendance
        WHERE YEAR(date)=%s AND MONTH(date)=%s
    """, (year, month))
    rows = cur.fetchall()

    days = {r["date"] for r in rows}
    total_days = len(days)

    summary = []
    for f in faculty:
        present_days = {r["date"] for r in rows if r["faculty_id"] == f["id"]}

        summary.append({
            "faculty_id": f["id"],
            "faculty_code": f["faculty_code"],
            "name": f["name"],
            "department": f["department"],
            "present": len(present_days),
            "total_days": total_days,
            "percentage": round((len(present_days) / total_days * 100), 2)
            if total_days > 0 else 0
        })

    return jsonify({
        "year": year,
        "month": month,
        "total_days": total_days,
        "summary": summary
    })

# ---------------------------
# RUN SERVER
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
