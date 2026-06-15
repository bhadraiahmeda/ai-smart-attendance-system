import os
import sqlite3
from pathlib import Path
BASE = Path(r"c:\Users\BHADRI\OneDrive\Desktop\ai-smart-attendance-system")
DB = BASE / "attendance.db"
if not DB.exists():
    DB = BASE / "backend" / "attendance.db"
print("Checking DB path:", DB)
print("Exists:", DB.exists(), "Size:", DB.stat().st_size if DB.exists() else 'N/A')
if DB.exists():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        admins = cur.execute("SELECT username, password FROM admins").fetchall()
        print('Admins:', admins)
    except Exception as e:
        print('Error reading admins table:', e)
    try:
        students = cur.execute("SELECT COUNT(*) as c FROM students").fetchone()
        print('Students count:', students['c'] if students else 'N/A')
    except Exception as e:
        print('Error reading students table:', e)
    conn.close()
else:
    print('No DB file found.')

# Check .env and environment variables
env_file = BASE / '.env'
print('.env exists:', env_file.exists())
if env_file.exists():
    print('.env contents:')
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            print('  ', line.strip())

print('ENV vars:')
for k in ['SECRET_KEY','EMAIL_SENDER','EMAIL_PASSWORD','EMAIL_HOST','EMAIL_PORT','RECOG_THRESHOLD']:
    print(f'  {k} =', os.environ.get(k, None))

# Check if attendance_graph.png (chart) exists
static_graph = BASE / 'frontend' / 'static' / 'attendance_graph.png'
print('attendance_graph.png exists:', static_graph.exists())
