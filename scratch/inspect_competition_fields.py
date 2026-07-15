"""Check competition_events columns and reward type of event 2."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3

db_file = "SSO_HC_backup_v1.4.0_1784081151.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get columns of competition_events
cursor.execute("PRAGMA table_info(competition_events)")
cols = cursor.fetchall()
print("competition_events columns:")
for c in cols:
    print(f"  {c[1]} ({c[2]})")

# Query event 2 fields
cursor.execute("SELECT * FROM competition_events WHERE id = 2")
row = cursor.fetchone()
col_names = [c[1] for c in cols]
print("\nEvent 2 details:")
for name, val in zip(col_names, row):
    print(f"  {name}: {val}")

conn.close()
