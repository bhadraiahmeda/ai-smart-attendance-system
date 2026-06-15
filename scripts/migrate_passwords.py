import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash
BASE = Path(r"c:\Users\BHADRI\OneDrive\Desktop\ai-smart-attendance-system")
DB = BASE / "attendance.db"
if not DB.exists():
    DB = BASE / "backend" / "attendance.db"
print('Migrating DB:', DB)
conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
cur = conn.cursor()
# Admins
try:
    admins = cur.execute("SELECT id, username, password FROM admins").fetchall()
    for a in admins:
        pwd = a['password']
        if pwd and (":" not in pwd and "$" not in pwd):
            print('Re-hashing admin', a['username'])
            cur.execute("UPDATE admins SET password=? WHERE id=?",
                        (generate_password_hash(pwd), a['id']))
except Exception as e:
    print('Admins migration error:', e)
# Students
try:
    studs = cur.execute("SELECT id, student_id, password FROM students").fetchall()
    for s in studs:
        spwd = s['password']
        if spwd and (":" not in spwd and "$" not in spwd):
            print('Re-hashing student id', s['student_id'])
            cur.execute("UPDATE students SET password=? WHERE id=?",
                        (generate_password_hash(spwd), s['id']))
except Exception as e:
    print('Students migration error:', e)
conn.commit()
conn.close()
print('Migration complete.')
