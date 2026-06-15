import sqlite3, os
from pathlib import Path
from werkzeug.security import check_password_hash
BASE = Path(r"c:\Users\BHADRI\OneDrive\Desktop\ai-smart-attendance-system")
DB = BASE / "attendance.db"
if not DB.exists():
    DB = BASE / "backend" / "attendance.db"
print('Using DB:', DB)
conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
cur = conn.cursor()
admin = cur.execute("SELECT username, password FROM admins LIMIT 1").fetchone()
print('Admin row:', dict(admin) if admin else None)
if admin:
    ok = check_password_hash(admin['password'], 'admin123')
    print('Default password admin123 matches hash?:', ok)

students = cur.execute("SELECT student_name, student_id, password, email FROM students LIMIT 5").fetchall()
print('Sample students:')
for s in students:
    print(dict(s))
    # show whether password equals student_id when checking hash
    try:
        match = check_password_hash(s['password'], s['student_id'])
    except Exception as e:
        match = 'error'
    print('  password matches student_id?:', match)
conn.close()
