import sqlite3
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db_path = "SSO_HC.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get some sample departments/departments
cur.execute("SELECT DISTINCT department FROM athletes")
depts = [r[0] for r in cur.fetchall()]
print("All unique departments:")
for d in depts:
    print(f" - {d}")

conn.close()
