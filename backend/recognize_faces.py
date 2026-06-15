import os
import csv
import pickle
from datetime import datetime

import cv2
import face_recognition

# Config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "face_data.pkl")
ATT_CSV = os.path.join(BASE_DIR, "attendance_logs", "attendance.csv")
UNKNOWN_DIR = os.path.join(BASE_DIR, "unknown_faces")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))


def send_email_smtp(student_name, receiver_email):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("[EMAIL] SMTP not configured; skipping email.")
        return False
    subject = "Attendance Marked Successfully"
    body = f"Hello,\n\nAttendance marked successfully for:\n{student_name}\n\nAI Smart Attendance System"
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = receiver_email
        with smtplib.SMTP("smtp.gmail.com", EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, receiver_email, msg.as_string())
        print("Email Sent Successfully")
        _log_email(receiver_email, subject, "SENT", "")
        return True
    except Exception as e:
        print("Email Error:", e)
        _log_email(receiver_email, subject, "FAILED", str(e))
        return False


def _log_email(to_email, subject, status, error):
    log_dir = os.path.dirname(ATT_CSV)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "email_logs.csv")
    with open(log_path, "a", newline="") as lf:
        csv.writer(lf).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            to_email, subject, status, error
        ])


def main():
    if not os.path.exists(MODEL_PATH):
        print("Model not found at", MODEL_PATH)
        return
    with open(MODEL_PATH, "rb") as file:
        known_faces, known_names = pickle.load(file)

    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not camera.isOpened():
        print("ERROR: Cannot open webcam.")
        return

    print("Starting Face Recognition...")
    marked_students = set()
    os.makedirs(UNKNOWN_DIR, exist_ok=True)

    while True:
        ret, frame = camera.read()
        if not ret:
            break
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        for face_encoding, face_location in zip(face_encodings, face_locations):
            name = "Unknown"
            if known_faces:
                distances = face_recognition.face_distance(known_faces, face_encoding)
                best_idx = None
                if len(distances) > 0:
                    best_idx = int(distances.argmin())
                    if distances[best_idx] < 0.52:
                        name = known_names[best_idx]

            if name == "Unknown":
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(UNKNOWN_DIR, f"unknown_{timestamp}.jpg")
                cv2.imwrite(path, frame)
                print("Unknown Image Saved:", path)

            top, right, bottom, left = face_location
            top *= 4; right *= 4; bottom *= 4; left *= 4
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            if name != "Unknown" and name not in marked_students:
                marked_students.add(name)
                now = datetime.now()
                date_str = now.strftime("%Y-%m-%d")
                time_str = now.strftime("%H:%M:%S")
                os.makedirs(os.path.dirname(ATT_CSV), exist_ok=True)
                with open(ATT_CSV, "a", newline="") as af:
                    csv.writer(af).writerow([name, date_str, time_str])
                print(f"Attendance Marked for {name}")
                # If students' emails are managed elsewhere, integrate here. SMTP optional.
                # send_email_smtp(name, receiver_email)

        cv2.imshow("AI Attendance System", frame)
        if cv2.waitKey(1) == ord('q'):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()