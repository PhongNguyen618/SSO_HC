import sqlite3
import os
import sys

# Connect to the live database
db_path = "SSO_HC.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} does not exist!")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables in DB:", tables)

# Get events
cur.execute("SELECT id, title, start_date, end_date, is_active FROM competition_events")
events = cur.fetchall()
print("\nEvents:")
for ev in events:
    print(f"ID: {ev[0]} | Title: {ev[1]} | Start: {ev[2]} | End: {ev[3]} | Active: {ev[4]}")

conn.close()
