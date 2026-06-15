import os
from dotenv import load_dotenv
LOCAL_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(LOCAL_BASE_DIR, ".env"))
RECOG_THRESHOLD = float(os.environ.get("RECOG_THRESHOLD", 0.52))
import csv
import pickle
import sqlite3
import smtplib
import threading
import numpy as np
import face_recognition as fr

import cv2
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import generate_password_hash, check_password_hash

from flask import (
    Flask, render_template, request,
    redirect, session, Response, send_file, flash, jsonify
)
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH      = os.path.join(BASE_DIR, "attendance.db")
DATASET_PATH = os.path.join(BASE_DIR, "dataset")
MODEL_PATH   = os.path.join(BASE_DIR, "models", "face_data.pkl")
CSV_PATH     = os.path.join(BASE_DIR, "attendance_logs", "attendance.csv")
PDF_PATH     = os.path.join(BASE_DIR, "Attendance_Report.pdf")
UNKNOWN_PATH = os.path.join(BASE_DIR, "unknown_faces")

# ── Email config (use environment variables in production) ────────────────────
EMAIL_SENDER   = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_HOST     = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT     = int(os.environ.get("EMAIL_PORT", "587"))
if not EMAIL_SENDER or not EMAIL_PASSWORD:
    print("[WARNING] EMAIL_SENDER or EMAIL_PASSWORD not set — email will fail until configured via environment variables.")

# ── Flask ──────────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "frontend", "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "ai_attendance_secret_2024")

# ── DB ─────────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

# ══════════════════════════════════════════════════════════════════════════════
# FACE MODEL — loaded ONCE at startup, reused every frame
# known_matrix : numpy array shape (N, 128)  — one averaged row per student
# known_names  : list of N name strings
# ══════════════════════════════════════════════════════════════════════════════
known_matrix = None          # numpy (N, 128) or None
known_names: list = []

def load_model():
    """Load pickle and convert to numpy matrix once."""
    global known_matrix, known_names
    if not os.path.exists(MODEL_PATH):
        known_matrix = None
        known_names  = []
        print("[MODEL] No model file — run Retrain first.")
        return
    with open(MODEL_PATH, "rb") as f:
        faces, known_names = pickle.load(f)
    if len(faces) == 0:
        known_matrix = None
        return
    # Convert to numpy matrix (N x 128) — works whether faces is a list or ndarray
    known_matrix = np.array(faces, dtype=np.float64)
    # Ensure rows are normalized (unit vectors) to match training normalization
    norms = np.linalg.norm(known_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    known_matrix = known_matrix / norms
    print(f"[MODEL] Loaded {len(known_names)} student(s): {known_names}")

load_model()

# ── Fast recogniser — vectorized numpy distance ────────────────────────────────
def _recognize_enc(enc: np.ndarray) -> str:
    """Compare one 128-d encoding against entire matrix in one numpy op."""
    if known_matrix is None or len(known_matrix) == 0:
        return "Unknown", None
    # Euclidean distance: sqrt(sum((A-B)^2)) for each row
    diffs  = known_matrix - enc          # (N, 128)
    dists  = np.sqrt((diffs ** 2).sum(axis=1))   # (N,)
    idx    = int(dists.argmin())
    best   = dists[idx]
    name   = known_names[idx] if best < RECOG_THRESHOLD else "Unknown"
    return name, float(best)

def _fast_recognize(frame):
    """
    1. Resize frame to 320px wide  — less pixels = faster HOG
    2. HOG with upsample=0         — skip pyramid, much faster
    3. Encode faces                — num_jitters=1, model=small
    4. Match with numpy vectorized distance (single matrix op per face)
    Returns (names list, boxes list in original frame coords)
    """
    h, w  = frame.shape[:2]
    tw    = 320
    th    = int(h * tw / w)
    small = cv2.resize(frame, (tw, th))
    rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

    locs  = fr.face_locations(rgb, number_of_times_to_upsample=0, model="hog")
    if not locs:
        return [], [], []

    encs  = fr.face_encodings(rgb, locs, num_jitters=1, model="small")
    sx, sy = w / tw, h / th

    names, boxes, confs = [], [], []
    for enc, loc in zip(encs, locs):
        name, dist = _recognize_enc(np.array(enc, dtype=np.float64))
        t = int(loc[0] * sy);  r = int(loc[1] * sx)
        b = int(loc[2] * sy);  l = int(loc[3] * sx)
        names.append(name)
        boxes.append((t, r, b, l))
        confs.append(None if dist is None else round(1.0 - dist, 3))
    return names, boxes, confs

def _draw_boxes(frame, names, boxes, confs=None):
    for i, (name, (t, r, b, l)) in enumerate(zip(names, boxes)):
        color = (0, 220, 90) if name != "Unknown" else (0, 60, 255)
        cv2.rectangle(frame, (l, t), (r, b), color, 2)
        cv2.rectangle(frame, (l, b - 26), (r, b), color, cv2.FILLED)
        label = name
        if confs and i < len(confs) and confs[i] is not None and name != "Unknown":
            label = f"{name} ({confs[i]*100:.0f}%)"
        cv2.putText(frame, label, (l + 5, b - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

# ══════════════════════════════════════════════════════════════════════════════
# ATTENDANCE — in-memory set avoids any DB read per frame
# ══════════════════════════════════════════════════════════════════════════════
_marked_today: set = set()   # lowercase names marked today
session_marked: dict = {}    # name -> time string (for current live session)
camera_status: dict = {"state": "Scanning", "message": "Waiting for faces...", "confidence": None}

def _load_marked_today():
    global _marked_today
    today = date.today().strftime("%Y-%m-%d")
    conn  = get_db()
    rows  = conn.execute(
        "SELECT student_name FROM attendance WHERE date=?", (today,)
    ).fetchall()
    conn.close()
    _marked_today = {r["student_name"].lower() for r in rows}

_load_marked_today()

def mark_attendance_db(student_name: str) -> bool:
    """Write to DB only once per student per day. All subsequent calls are instant."""
    global _marked_today
    key = student_name.lower()
    if key in _marked_today:      # O(1) set lookup — no DB, no disk
        return False
    _marked_today.add(key)        # block further calls instantly
    today = date.today().strftime("%Y-%m-%d")
    now   = datetime.now().strftime("%H:%M:%S")
    conn  = get_db()
    conn.execute(
        "INSERT INTO attendance (student_name, date, time) VALUES (?,?,?)",
        (student_name, today, now),
    )
    conn.commit()
    conn.close()
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "a", newline="") as f:
        csv.writer(f).writerow([student_name, today, now])
    print(f"[ATTENDANCE] {student_name} marked at {now}")
    return True

# ── Camera ─────────────────────────────────────────────────────────────────────
camera         = None
camera_running = False

def open_camera():
    global camera, camera_running
    if camera and camera.isOpened():
        camera.release()
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camera_running = True

def close_camera():
    global camera, camera_running
    camera_running = False
    if camera and camera.isOpened():
        camera.release()
    camera = None

# ── Live video stream ──────────────────────────────────────────────────────────
def generate_live_frames():
    global session_marked
    session_marked = {}
    _load_marked_today()          # sync with today's DB on session start
    frame_n    = 0
    last_names = []
    last_boxes = []

    while camera_running:
        if not camera or not camera.isOpened():
            break
        ok, frame = camera.read()
        if not ok:
            continue

        frame_n += 1
        if frame_n % 2 == 0:     # process every 2nd frame
            last_names, last_boxes, last_confs = _fast_recognize(frame)
            now_str = datetime.now().strftime("%H:%M:%S")
            if not last_names:
                camera_status.update({"state": "Scanning", "message": "Scanning for faces...", "confidence": None})
            for name, conf in zip(last_names, last_confs):
                if name == "Unknown":
                    camera_status.update({"state": "Unknown Face", "message": "Face not recognized.", "confidence": None})
                    continue
                if name in session_marked:
                    camera_status.update({"state": "Already Marked Today", "message": f"{name} already marked.", "confidence": conf})
                    continue
                if name.lower() in _marked_today:
                    session_marked[name] = {"time": now_str, "confidence": conf}
                    camera_status.update({"state": "Already Marked Today", "message": f"{name} already marked today.", "confidence": conf})
                    continue
                # Only reaches DB once per new student
                if mark_attendance_db(name):
                    session_marked[name] = {"time": now_str, "confidence": conf, "email_sent": False}
                    conn = get_db()
                    student = conn.execute(
                        "SELECT email FROM students WHERE LOWER(student_name)=LOWER(?)",
                        (name.lower(),)
                    ).fetchone()
                    conn.close()
                    if student and student["email"]:
                        send_present_email(name, student["email"], now_str)
                        session_marked[name]["email_sent"] = True

        _draw_boxes(frame, last_names, last_boxes, last_confs if 'last_confs' in locals() else None)
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

# ── Dashboard video stream (admin) ────────────────────────────────────────────
_dash_camera = None

def generate_dash_frames():
    global _dash_camera
    if _dash_camera and _dash_camera.isOpened():
        _dash_camera.release()
    _dash_camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    _dash_camera.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    _dash_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    _dash_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    frame_n, last_names, last_boxes = 0, [], []
    while True:
        if not _dash_camera or not _dash_camera.isOpened():
            break
        ok, frame = _dash_camera.read()
        if not ok:
            continue
        frame_n += 1
        if frame_n % 2 == 0:
            last_names, last_boxes, last_confs = _fast_recognize(frame)
            for name in last_names:
                if name != "Unknown" and name.lower() not in _marked_today:
                    mark_attendance_db(name)
        _draw_boxes(frame, last_names, last_boxes, last_confs if 'last_confs' in locals() else None)
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

# ── DB helpers ─────────────────────────────────────────────────────────────────
def get_today_stats():
    today = date.today().strftime("%Y-%m-%d")
    conn  = get_db()
    total   = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    present = conn.execute(
        "SELECT COUNT(DISTINCT student_name) FROM attendance WHERE date=?", (today,)
    ).fetchone()[0]
    conn.close()
    absent = max(total - present, 0)
    pct    = round(present / total * 100, 2) if total else 0
    return total, present, absent, pct

def get_recent_attendance(limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT student_name, date, time FROM attendance ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows

def get_student_stats_and_history(student_name):
    """Single DB connection for both stats and history — fast student login."""
    conn = get_db()
    # All student attendance rows in one query
    rows = conn.execute(
        "SELECT date, time FROM attendance WHERE LOWER(student_name)=LOWER(?) ORDER BY id DESC",
        (student_name,)
    ).fetchall()
    # Total distinct class days in one query
    total_days = conn.execute(
        "SELECT COUNT(DISTINCT date) FROM attendance"
    ).fetchone()[0] or 1
    conn.close()

    present = len(rows)
    absent  = max(total_days - present, 0)
    pct     = round(present / total_days * 100, 2)
    history = [{"date": r["date"], "time": r["time"]} for r in rows]
    return present, absent, pct, history

# ── Email helpers ──────────────────────────────────────────────────────────────
def _send_mail(to_email, subject, html_body):
    log_path = os.path.join(os.path.dirname(CSV_PATH), "email_logs.csv")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        if not EMAIL_SENDER or not EMAIL_PASSWORD or "your." in EMAIL_SENDER or "your-" in EMAIL_PASSWORD:
            raise ValueError("EMAIL_SENDER or EMAIL_PASSWORD not configured in .env (still placeholder)")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=10) as s:
            s.ehlo()
            s.starttls()
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        print(f"[EMAIL SENT] to={to_email} subject={subject}", flush=True)
        with open(log_path, "a", newline="") as lf:
            csv.writer(lf).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                to_email, subject, "SENT", ""
            ])
        return True
    except smtplib.SMTPException as e:
        err = str(e)
        print(f"[SMTP ERROR] to={to_email} subject={subject} error={err}", flush=True)
        with open(log_path, "a", newline="") as lf:
            csv.writer(lf).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                to_email, subject, "SMTP ERROR", err
            ])
        return False
    except Exception as e:
        err = str(e)
        print(f"[EMAIL FAILED] to={to_email} subject={subject} error={err}", flush=True)
        with open(log_path, "a", newline="") as lf:
            csv.writer(lf).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                to_email, subject, "FAILED", err
            ])
        return False

def send_present_email(name, email, time_str):
    today = date.today().strftime("%d %B %Y")
    html  = f"""
    <div style="font-family:Segoe UI,sans-serif;max-width:520px;margin:auto;background:#fff;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#16a34a,#15803d);padding:28px 32px;text-align:center;">
        <h2 style="color:#fff;margin:0;">✅ Attendance Confirmed</h2>
      </div>
      <div style="padding:28px 32px;">
        <p>Hello <strong>{name}</strong>,</p>
        <p style="color:#6b7280;">Your attendance has been marked successfully.</p>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:16px 20px;margin:20px 0;">
          <p style="margin:4px 0;color:#166534;"><strong>📅 Date:</strong> {today}</p>
          <p style="margin:4px 0;color:#166534;"><strong>⏰ Time:</strong> {time_str}</p>
          <p style="margin:4px 0;color:#166534;"><strong>✅ Status:</strong> Present</p>
        </div>
        <p style="color:#9ca3af;font-size:.85rem;">AI Smart Attendance System</p>
      </div>
    </div>"""
    threading.Thread(target=_send_mail,
                     args=(email, f"✅ Attendance Marked – {today}", html),
                     daemon=True).start()

def send_absent_email(name, email):
    today = date.today().strftime("%d %B %Y")
    html  = f"""
    <div style="font-family:Segoe UI,sans-serif;max-width:520px;margin:auto;background:#fff;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#dc2626,#b91c1c);padding:28px 32px;text-align:center;">
        <h2 style="color:#fff;margin:0;">⚠️ Absence Alert</h2>
      </div>
      <div style="padding:28px 32px;">
        <p>Hello <strong>{name}</strong>,</p>
        <p style="color:#6b7280;">You were <strong>absent</strong> from today's session.</p>
        <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:16px 20px;margin:20px 0;">
          <p style="margin:4px 0;color:#991b1b;"><strong>📅 Date:</strong> {today}</p>
          <p style="margin:4px 0;color:#991b1b;"><strong>❌ Status:</strong> Absent</p>
        </div>
        <p style="color:#6b7280;">Please attend regularly to maintain a good record.</p>
        <p style="color:#9ca3af;font-size:.85rem;">AI Smart Attendance System</p>
      </div>
    </div>"""
    threading.Thread(target=_send_mail,
                     args=(email, f"⚠️ Absence Alert – {today}", html),
                     daemon=True).start()

# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/save_student", methods=["POST"])
def save_student():
    student_name = request.form.get("student_name", "").strip()
    student_id   = request.form.get("student_id",   "").strip()
    department   = request.form.get("department",   "").strip()
    year         = request.form.get("year",         "").strip()
    email        = request.form.get("email",        "").strip()

    if not all([student_name, student_id, department, year, email]):
        return render_template("register.html", error="All fields are required.")

    conn = get_db()
    try:
        if conn.execute("SELECT id FROM students WHERE student_id=?", (student_id,)).fetchone():
            conn.close()
            return render_template("register.html",
                error=f"Student ID '{student_id}' already exists.")
        # store hashed password (default password = student_id)
        hashed_pwd = generate_password_hash(student_id)
        conn.execute(
            "INSERT INTO students (student_name,student_id,password,department,year,email) VALUES (?,?,?,?,?,?)",
            (student_name, student_id, hashed_pwd, department, year, email))
        conn.commit()
    except Exception as e:
        conn.close()
        conn2 = get_db()
        try:
            conn2.execute("ALTER TABLE students ADD COLUMN email TEXT DEFAULT ''")
            conn2.execute(
                "INSERT INTO students (student_name,student_id,password,department,year,email) VALUES (?,?,?,?,?,?)",
                (student_name, student_id, hashed_pwd, department, year, email))
            conn2.commit()
        except Exception as e2:
            conn2.close()
            return render_template("register.html", error=str(e2))
        conn2.close()
    else:
        conn.close()

    # Create dataset folder immediately
    from capture_faces import capture_student_faces
    dataset_folder = os.path.join(DATASET_PATH, student_name)
    os.makedirs(dataset_folder, exist_ok=True)

    # Perform heavy webcam capture and model training in background
    def _bg_capture_and_train(name):
        try:
            capture_student_faces(name)
            from train_model import train_model
            train_model()
            load_model()
        except Exception as e:
            print(f"Background capture/train error for {name}:", e)

    t = threading.Thread(target=_bg_capture_and_train, args=(student_name,), daemon=True)
    t.start()

    return render_template("registration_success.html",
        student_name=student_name, student_id=student_id,
        department=department, year=year, email=email,
        dataset_folder=dataset_folder)

SESSION_MINUTES = 2   # change to adjust live session duration

@app.route("/live_camera")
def live_camera():
    open_camera()
    return render_template("live_camera.html", session_minutes=SESSION_MINUTES)

@app.route("/live_video_feed")
def live_video_feed():
    return Response(generate_live_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/attendance_updates")
def attendance_updates():
    total, present, absent, _ = get_today_stats()
    marked = []
    for k, v in session_marked.items():
        if isinstance(v, dict):
            marked.append({"name": k, "time": v.get("time"), "confidence": v.get("confidence")})
        else:
            marked.append({"name": k, "time": v})
    return jsonify({"present": present, "absent": absent, "marked": marked, "camera_status": camera_status})

@app.route("/download_excel")
def download_excel():
    if "admin" not in session:
        return redirect("/login")
    conn = get_db()
    rows = conn.execute(
        "SELECT student_name, date, time FROM attendance ORDER BY id"
    ).fetchall()
    conn.close()
    records = [{"Name": r["student_name"], "Date": r["date"], "Time": r["time"]} for r in rows]
    df = pd.DataFrame(records)
    excel_path = os.path.join(os.path.dirname(CSV_PATH), "attendance_report.xlsx")
    df.to_excel(excel_path, index=False, engine="openpyxl")
    return send_file(excel_path, as_attachment=True)

@app.route("/stop_camera", methods=["POST"])
def stop_camera():
    global session_marked
    close_camera()
    today = date.today().strftime("%Y-%m-%d")
    conn  = get_db()
    try:
        all_students = conn.execute("SELECT student_name, email FROM students").fetchall()
    except Exception:
        all_students = []
    present_rows = conn.execute(
        "SELECT LOWER(student_name) as nm FROM attendance WHERE date=?", (today,)
    ).fetchall()
    conn.close()
    present_set  = {r["nm"] for r in present_rows}
    emails_sent  = []
    for s in all_students:
        name  = s["student_name"]
        email = s["email"] if s["email"] else None
        if not email:
            continue
        if name.lower() in present_set:
            entry = session_marked.get(name)
            if isinstance(entry, dict) and entry.get("email_sent"):
                continue
            if isinstance(entry, dict):
                time_str = entry.get("time", datetime.now().strftime("%H:%M:%S"))
            else:
                time_str = entry if entry else datetime.now().strftime("%H:%M:%S")
            send_present_email(name, email, time_str)
            emails_sent.append({"name": name, "email": email, "type": "present"})
        else:
            send_absent_email(name, email)
            emails_sent.append({"name": name, "email": email, "type": "absent"})
    session_marked = {}
    return jsonify({"status": "ok", "emails": emails_sent})

@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    error = None
    if request.method == "POST":
        sid = request.form.get("student_id", "").strip()
        pwd = request.form.get("password",   "").strip()
        conn = get_db()
        student = conn.execute(
            "SELECT * FROM students WHERE student_id=?", (sid,)
        ).fetchone()
        conn.close()
        if student and check_password_hash(student["password"], pwd):
            present, absent, pct, history = get_student_stats_and_history(student["student_name"])
            return render_template("student_dashboard.html",
                student_name=student["student_name"],
                student_id=student["student_id"],
                department=student["department"],
                year=student["year"],
                present_count=present,
                absent_count=absent,
                attendance_percentage=pct,
                attendance_history=history)
        error = "Invalid Student ID or Password."
    return render_template("student_login.html", error=error)

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        conn = get_db()
        admin = conn.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password"], password):
            session["admin"] = username
            return redirect("/dashboard")
        error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/login")
    total, present, absent, pct = get_today_stats()
    records = get_recent_attendance()
    return render_template("dashboard.html",
        total_students=total, present_today=present,
        absent_today=absent, attendance_percentage=pct,
        attendance_records=records)

@app.route("/video_feed")
def video_feed():
    if "admin" not in session:
        return redirect("/login")
    return Response(generate_dash_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/students")
def students():
    if "admin" not in session:
        return redirect("/login")
    conn = get_db()
    all_students = conn.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("students.html", students=all_students)

@app.route("/edit_student/<int:sid>", methods=["GET", "POST"])
def edit_student(sid):
    if "admin" not in session:
        return redirect("/login")
    conn = get_db()
    if request.method == "POST":
        conn.execute(
            "UPDATE students SET student_name=?,department=?,year=?,email=? WHERE id=?",
            (request.form.get("student_name","").strip(),
             request.form.get("department","").strip(),
             request.form.get("year","").strip(),
             request.form.get("email","").strip(), sid))
        conn.commit()
        conn.close()
        return redirect("/students")
    student = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    conn.close()
    return render_template("edit_student.html", student=student)

@app.route("/delete_student/<int:sid>")
def delete_student(sid):
    if "admin" not in session:
        return redirect("/login")
    conn = get_db()
    conn.execute("DELETE FROM students WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return redirect("/students")

@app.route("/analytics")
def analytics():
    if "admin" not in session:
        return redirect("/login")
    conn = get_db()
    rows = conn.execute(
        "SELECT student_name, COUNT(*) as cnt FROM attendance GROUP BY LOWER(student_name) ORDER BY cnt DESC"
    ).fetchall()
    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    today = date.today().strftime("%Y-%m-%d")
    present_today = conn.execute(
        "SELECT COUNT(DISTINCT student_name) FROM attendance WHERE date=?",
        (today,)
    ).fetchone()[0]
    absent_today = max(total_students - present_today, 0)
    attendance_rate = round((present_today / total_students) * 100, 2) if total_students else 0
    month_rows = conn.execute(
        "SELECT SUBSTR(date, 1, 7) as month, COUNT(*) as cnt FROM attendance GROUP BY month ORDER BY month DESC"
    ).fetchall()
    dept_rows = conn.execute(
        "SELECT s.department as department, COUNT(a.id) as cnt FROM attendance a "
        "JOIN students s ON LOWER(a.student_name)=LOWER(s.student_name) "
        "GROUP BY LOWER(s.department) ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    graph_image = None
    if rows:
        names  = [r["student_name"] for r in rows]
        counts = [r["cnt"] for r in rows]
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        axes[0].bar(names, counts, color="#2563eb")
        axes[0].set_title("Attendance Count per Student")
        axes[0].set_xlabel("Student")
        axes[0].set_ylabel("Days Present")
        axes[0].tick_params(axis="x", rotation=30)
        axes[1].pie(counts, labels=names, autopct="%1.1f%%", startangle=140)
        axes[1].set_title("Attendance Distribution")
        plt.tight_layout()
        graph_path = os.path.join(app.static_folder, "attendance_graph.png")
        plt.savefig(graph_path, bbox_inches="tight")
        plt.close()
        graph_image = "attendance_graph.png"
    return render_template(
        "analytics.html",
        graph_image=graph_image,
        rows=rows,
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        attendance_rate=attendance_rate,
        month_rows=month_rows,
        dept_rows=dept_rows,
    )

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if "admin" not in session:
        return redirect("/login")
    conn      = get_db()
    msg, error = None, None
    total_stu = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    db_size   = round(os.path.getsize(DB_PATH) / 1024, 2) if os.path.exists(DB_PATH) else 0
    if request.method == "POST":
        current = request.form.get("current_password", "").strip()
        new_pwd = request.form.get("new_password",     "").strip()
        confirm = request.form.get("confirm_password", "").strip()
        admin = conn.execute(
            "SELECT * FROM admins WHERE username=?", (session["admin"],)
        ).fetchone()
        if not admin or not check_password_hash(admin["password"], current):
            error = "Current password is incorrect."
        elif new_pwd != confirm:
            error = "New passwords do not match."
        elif len(new_pwd) < 4:
            error = "Password must be at least 4 characters."
        else:
            conn.execute("UPDATE admins SET password=? WHERE username=?",
                         (generate_password_hash(new_pwd), session["admin"]))
            conn.commit()
            msg = "Password updated successfully!"
    conn.close()
    return render_template("settings.html", total_students=total_stu,
                           db_size=db_size, db_path=DB_PATH,
                           message=msg, error=error)


@app.route('/admin/send_test_email', methods=['GET', 'POST'])
def send_test_email():
    if 'admin' not in session:
        return redirect('/login')
    to_addr = request.values.get('to') or EMAIL_SENDER
    if not to_addr or "your." in to_addr:
        return jsonify({'status': 'error', 'message': 'No real recipient configured (EMAIL_SENDER in .env is still a placeholder).'}), 400
    subject = 'Test Email from AI Smart Attendance'
    html = '<div style="font-family:Segoe UI,sans-serif;padding:20px;"><h3>Test Email</h3><p>This is a test email sent from your AI Smart Attendance installation.</p></div>'
    ok = _send_mail(to_addr, subject, html)
    if ok:
        return jsonify({'status': 'ok', 'to': to_addr})
    return jsonify({'status': 'failed', 'to': to_addr}), 500


@app.route('/admin/email_logs')
def email_logs():
    if 'admin' not in session:
        return redirect('/login')
    log_path = os.path.join(os.path.dirname(CSV_PATH), "email_logs.csv")
    logs = []
    if os.path.exists(log_path):
        with open(log_path, 'r', newline='', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 4:
                    logs.append({'time': parts[0], 'to': parts[1], 'subject': parts[2], 'status': parts[3], 'error': parts[4] if len(parts) > 4 else ''})
    logs.reverse()  # Newest first
    return render_template('email_logs.html', logs=logs, email_sender=EMAIL_SENDER, email_configured=EMAIL_SENDER and not "your." in EMAIL_SENDER)


@app.route("/download_attendance")
def download_attendance():
    if "admin" not in session:
        return redirect("/login")
    conn = get_db()
    rows = conn.execute(
        "SELECT student_name, date, time FROM attendance ORDER BY id"
    ).fetchall()
    conn.close()
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Name", "Date", "Time"])
        for r in rows:
            w.writerow([r["student_name"], r["date"], r["time"]])
    return send_file(CSV_PATH, as_attachment=True)

@app.route("/download_pdf")
def download_pdf():
    if "admin" not in session:
        return redirect("/login")
    conn = get_db()
    rows = conn.execute(
        "SELECT student_name, date, time FROM attendance ORDER BY date DESC, time DESC"
    ).fetchall()
    conn.close()
    doc  = SimpleDocTemplate(PDF_PATH, pagesize=A4)
    data = [["#", "Student Name", "Date", "Time"]]
    for i, r in enumerate(rows, 1):
        data.append([str(i), r["student_name"], r["date"], r["time"]])
    table = Table(data, colWidths=[30, 180, 100, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#2563eb")),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4ff")]),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    doc.build([table])
    return send_file(PDF_PATH, as_attachment=True)

@app.route("/retrain")
def retrain():
    if "admin" not in session:
        return redirect("/login")
    from train_model import train_model
    train_model()
    load_model()
    flash("Model retrained successfully!", "success")
    return redirect("/dashboard")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from database import init_db
    init_db()
    conn = get_db()
    try:
        conn.execute("ALTER TABLE students ADD COLUMN email TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    # Add index for fast student attendance lookups
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_att_name ON attendance(student_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_att_date ON attendance(date)")
        conn.commit()
    except Exception:
        pass
    conn.close()
    app.run(debug=True, use_reloader=False)
