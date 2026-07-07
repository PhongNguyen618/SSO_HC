import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

new_backup = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(new_backup)
cur = conn.cursor()

cur.execute("SELECT id, full_name, strava_refresh_token IS NOT NULL as linked FROM athletes WHERE full_name LIKE '%Minh T%'")
rows = cur.fetchall()
print(f"=== BACKUP MOI ({new_backup}) ===")
for r in rows:
    aid, name, linked = r
    print(f"  ID={aid}, Ten={name}, Linked={linked}")
    cur.execute("SELECT event_id FROM competition_registrations WHERE athlete_id = ?", (aid,))
    regs = [x[0] for x in cur.fetchall()]
    print(f"    Giai: {regs}")
    cur.execute("SELECT COUNT(*), MIN(activity_date), MAX(activity_date) FROM activities WHERE athlete_id = ?", (aid,))
    cnt, mn, mx = cur.fetchone()
    print(f"    Acts: {cnt} ({mn} -> {mx})")
    cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ? AND activity_date >= '2026-06-16'", (aid,))
    print(f"    Acts tu 16/6: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM activities")
print(f"\nTong acts backup moi: {cur.fetchone()[0]}")
conn.close()

old_backup = "SSO_HC_backup_v1.4.0_1783161208.db"
conn2 = sqlite3.connect(old_backup)
cur2 = conn2.cursor()
cur2.execute("SELECT COUNT(*) FROM activities")
print(f"Tong acts backup cu: {cur2.fetchone()[0]}")
conn2.close()

live = "SSO_HC.db"
conn3 = sqlite3.connect(live)
cur3 = conn3.cursor()
cur3.execute("SELECT id, full_name, strava_refresh_token IS NOT NULL as linked FROM athletes WHERE full_name LIKE '%Minh T%'")
rows3 = cur3.fetchall()
print(f"\n=== DB LIVE ===")
for r in rows3:
    aid, name, linked = r
    print(f"  ID={aid}, Ten={name}, Linked={linked}")
    cur3.execute("SELECT event_id FROM competition_registrations WHERE athlete_id = ?", (aid,))
    regs = [x[0] for x in cur3.fetchall()]
    print(f"    Giai: {regs}")
    cur3.execute("SELECT COUNT(*), MIN(activity_date), MAX(activity_date) FROM activities WHERE athlete_id = ?", (aid,))
    cnt, mn, mx = cur3.fetchone()
    print(f"    Acts: {cnt} ({mn} -> {mx})")
conn3.close()
