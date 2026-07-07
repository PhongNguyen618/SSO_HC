import sqlite3

db = "SSO_HC_backup_v1.4.0_1783161208.db"
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM activities")
print(f"Total activities: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM activities WHERE event_id = 1 AND activity_date < '2026-06-16'")
print(f"SSO HC truoc 16/6: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(DISTINCT athlete_id) FROM activities WHERE event_id = 1 AND activity_date < '2026-06-16'")
print(f"So VDV truoc 16/6: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM activities WHERE event_id = 1")
print(f"SSO HC tong: {cur.fetchone()[0]}")

conn.close()
