import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "attendance.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def get_today_stats():
    """Return (present_today, absent_today, attendance_percentage) for today."""
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(DISTINCT student_name) FROM attendance WHERE date = ?",
        (today,)
    )
    present_today = cursor.fetchone()[0]
    conn.close()

    absent_today = max(total_students - present_today, 0)
    percentage = round((present_today / total_students) * 100, 2) if total_students else 0

    return total_students, present_today, absent_today, percentage


def get_recent_attendance(limit=50):
    """Return the most recent attendance rows."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT student_name, date, time FROM attendance ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_student_attendance(student_name):
    """Return (present_count, absent_count, percentage) for a student.
       Uses actual DB rows; total is derived from distinct dates with any attendance.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Count days the student was present
    cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE LOWER(student_name) = LOWER(?)",
        (student_name,)
    )
    present_count = cursor.fetchone()[0]

    # Total class days = distinct dates that have any attendance record
    cursor.execute("SELECT COUNT(DISTINCT date) FROM attendance")
    total_classes = cursor.fetchone()[0] or 1
    conn.close()

    absent_count = max(total_classes - present_count, 0)
    percentage = round((present_count / total_classes) * 100, 2)
    return present_count, absent_count, percentage


def get_attendance_history(student_name):
    """Return list of {date, time} dicts for a student."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date, time FROM attendance WHERE LOWER(student_name) = LOWER(?) ORDER BY id DESC",
        (student_name,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"date": r["date"], "time": r["time"]} for r in rows]


def mark_attendance(student_name):
    """Insert one attendance record; prevents duplicate for same student on same date."""
    from datetime import datetime
    now  = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM attendance WHERE LOWER(student_name) = LOWER(?) AND date = ?",
        (student_name, date)
    )
    if cursor.fetchone():
        conn.close()
        return False  # already marked today

    cursor.execute(
        "INSERT INTO attendance (student_name, date, time) VALUES (?, ?, ?)",
        (student_name, date, time)
    )
    conn.commit()
    conn.close()
    return True
