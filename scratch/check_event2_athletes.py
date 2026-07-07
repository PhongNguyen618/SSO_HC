import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(backup_db)
cur = conn.cursor()

# Lấy danh sách VĐV tham gia giải 2 và số lượng hoạt động của họ ở giải 2
cur.execute("""
    SELECT a.id, a.full_name, a.strava_refresh_token IS NOT NULL as linked, COUNT(act.id) as act_cnt 
    FROM athletes a 
    JOIN competition_registrations cr ON a.id = cr.athlete_id 
    LEFT JOIN activities act ON a.id = act.athlete_id AND act.event_id = 2 
    WHERE cr.event_id = 2 
    GROUP BY a.id, a.full_name, linked
    ORDER BY linked DESC, act_cnt DESC
""")
rows = cur.fetchall()
print("=== THỐNG KÊ VĐV GIẢI 2 TRONG BACKUP ===")
for r in rows:
    print(f"ID={r[0]}: {r[1]} - Linked: {r[2]} - Hoạt động giải 2: {r[3]}")

conn.close()
