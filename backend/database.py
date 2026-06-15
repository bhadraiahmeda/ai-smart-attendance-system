import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "attendance.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT    NOT NULL,
            student_id   TEXT    UNIQUE NOT NULL,
            password     TEXT    NOT NULL,
            department   TEXT,
            year         TEXT,
            email        TEXT    DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            date         TEXT NOT NULL,
            time         TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Add email column if upgrading from older DB
    try:
        cur.execute("ALTER TABLE students ADD COLUMN email TEXT DEFAULT ''")
    except Exception:
        pass

    # Default admin (store hashed password)
    if not cur.execute("SELECT 1 FROM admins WHERE username='admin'").fetchone():
        cur.execute(
            "INSERT INTO admins (username, password) VALUES (?,?)",
            ("admin", generate_password_hash("admin123")),
        )

    conn.commit()
    conn.close()
    print("Database ready.")
    print("Default admin  ->  username: admin  |  password: admin123")


if __name__ == "__main__":
    init_db()
