import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(backup_db)
cur = conn.cursor()

# Lấy chi tiết hoạt động '19190105196_2' đang gán cho Lê Tuấn Anh (ID=123)
cur.execute("""
    SELECT id, athlete_id, athlete_name_raw, name, distance_km, activity_date, activity_time
    FROM activities
    WHERE id = '19190105196_2'
""")
act = cur.fetchone()
print("=== CHI TIẾT HOẠT ĐỘNG 19190105196_2 ===")
if act:
    print(f"ID Hoạt Động: {act[0]}")
    print(f"Gán cho Athlete ID trong DB: {act[1]}")
    print(f"Tên thô lấy từ Strava (athlete_name_raw): {act[2]}")
    print(f"Tên bài chạy: {act[3]}")
    print(f"Quãng đường: {act[4]} km")
    print(f"Ngày chạy: {act[5]} | Giờ chạy: {act[6]}")
else:
    print("Không tìm thấy hoạt động 19190105196_2")

# Truy vấn thông tin của VĐV Lê Tuấn Anh (ID=123) và VĐV Trần Trọng Hoan (ID=92)
print("\n=== THÔNG TIN VĐV LIÊN QUAN ===")
cur.execute("SELECT id, full_name, strava_name, strava_athlete_id FROM athletes WHERE id IN (123, 92)")
for row in cur.fetchall():
    print(f"ID={row[0]} | Tên DB={row[1]} | Tên Strava={row[2]} | Strava ID={row[3]}")

conn.close()
