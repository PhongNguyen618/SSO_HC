import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(backup_db)
cur = conn.cursor()

# Kiểm tra thông tin VĐV Lê Tuấn Anh (ID=123)
cur.execute("SELECT id, full_name, strava_name, strava_athlete_id FROM athletes WHERE id = 123")
print("=== VĐV LÊ TUẤN ANH (ID=123) ===")
print(cur.fetchone())

# Kiểm tra xem hoạt động 19028650701_2 ban đầu có phải là của Lê Tuấn Anh không?
# Xem trong các hoạt động của Lê Tuấn Anh
cur.execute("SELECT id, athlete_name_raw, name, distance_km FROM activities WHERE athlete_id = 123 LIMIT 5")
print("\n=== CÁC HOẠT ĐỘNG CỦA LÊ TUẤN ANH ===")
for r in cur.fetchall():
    print(r)

# Thống kê xem có bao nhiêu hoạt động của Nguyễn Minh Tú (ID=102) bị gán cho Lê Tuấn Anh (ID=123)
cur.execute("""
    SELECT COUNT(*) FROM activities 
    WHERE athlete_id = 123 AND id LIKE '%_2' AND (
        id LIKE '19028650701%' OR
        id LIKE '19056089600%' OR
        id LIKE '19104555898%' OR
        id LIKE '19116745507%' OR
        id LIKE '19130432904%' OR
        id LIKE '19143922408%' OR
        id LIKE '19156838810%' OR
        id LIKE '19163878254%' OR
        id LIKE '19164191659%' OR
        id LIKE '19169263862%' OR
        id LIKE '19175277780%' OR
        id LIKE '19182383063%' OR
        id LIKE '19190105196%'
    )
""")
print(f"\nSố hoạt động của Tú bị gán nhầm cho Lê Tuấn Anh: {cur.fetchone()[0]}")

conn.close()
