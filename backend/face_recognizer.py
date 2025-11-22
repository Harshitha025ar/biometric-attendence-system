import os
import cv2
import numpy as np
from config import DATASET_DIR, MODEL_PATH

class FaceRecognizer:
    def __init__(self):
        # Face detector
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        # LBPH recognizer
        self.recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )

        self.trained = False

        if os.path.exists(MODEL_PATH):
            try:
                self.recognizer.read(MODEL_PATH)
                self.trained = True
                print("[MODEL] Loaded LBPH model.")
            except:
                print("[MODEL] Failed to load. Will retrain.")

    def _load_dataset(self):
        images, labels = [], []

        for file in os.listdir(DATASET_DIR):
            if not file.endswith(".jpg"): 
                continue

            try:
                faculty_id = int(file.split("_")[0])
            except:
                continue

            img = cv2.imread(os.path.join(DATASET_DIR, file), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue

            images.append(img)
            labels.append(faculty_id)

        return images, np.array(labels)

    def train_model(self):
        images, labels = self._load_dataset()

        if len(images) == 0:
            print("[TRAIN] No images available.")
            return

        print(f"[TRAIN] Training with {len(images)} images...")
        self.recognizer.train(images, labels)
        self.recognizer.write(MODEL_PATH)
        self.trained = True
        print("[TRAIN] Saved LBPH model.")

    def recognize_faces(self, frame):
        results = []

        if frame is None or not self.trained:
            return results

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(80,80)
        )

        for (x, y, w, h) in faces:
            roi = gray[y:y+h, x:x+w]

            try:
                label, dist = self.recognizer.predict(roi)
            except:
                continue

            confidence = max(0, 100 - min(dist, 100))

            if confidence < 40:
                continue

            results.append({
                "faculty_id": label,
                "confidence": confidence,
                "box": [x, y, w, h]
            })

        return results
