import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(backup_db)
cur = conn.cursor()

# Lấy thông tin hoạt động có ID '19028650701_2'
cur.execute("""
    SELECT id, athlete_id, athlete_name_raw, name, activity_date, distance_km 
    FROM activities 
    WHERE id LIKE '19028650701%'
""")
rows = cur.fetchall()
print("=== THÔNG TIN HOẠT ĐỘNG TRÙNG ID ===")
for r in rows:
    print(f"Act ID: {r[0]} | Athlete ID: {r[1]} | Tên VĐV: {r[2]} | Tên bài: {r[3]} | Ngày: {r[4]} | Quãng đường: {r[5]}")

# Kiểm tra xem có athlete nào khác trùng strava_athlete_id với Nguyễn Minh Tú (42307924) không?
cur.execute("""
    SELECT id, full_name, strava_athlete_id, strava_name 
    FROM athletes 
    WHERE strava_athlete_id = '42307924'
""")
athletes = cur.fetchall()
print("\n=== VĐV CÓ CÙNG STRAVA ATHLETE ID ===")
for a in athletes:
    print(f"Athlete ID: {a[0]} | Tên: {a[1]} | Strava ID: {a[2]} | Strava Name: {a[3]}")

conn.close()
