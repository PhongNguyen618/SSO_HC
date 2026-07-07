import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(backup_db)
cur = conn.cursor()

# Tìm tất cả các hoạt động dạng API (ID không phải băm 64 ký tự) mà athlete_id trong activities 
# không khớp với strava_athlete_id của athlete tương ứng trong DB.
# Tức là: ta lấy strava_athlete_id từ bảng athletes, so sánh với id hoạt động.
# Tuy nhiên, cách dễ nhất là quét qua bảng activities, lấy các hoạt động có ID dạng số_eventId.
# Sau đó lấy thông tin athlete hiện tại của hoạt động đó, và so sánh xem athlete đó có strava_athlete_id khớp với thông tin thật không.

cur.execute("""
    SELECT act.id, act.athlete_id, act.athlete_name_raw, a.full_name, a.strava_athlete_id
    FROM activities act
    JOIN athletes a ON act.athlete_id = a.id
    WHERE length(act.id) < 60
""")
rows = cur.fetchall()

print("=== KIỂM TRA MAPPING HOẠT ĐỘNG TRONG BACKUP ===")
mismatches = 0
for r in rows:
    act_id, ath_id, act_name_raw, ath_full_name, strava_ath_id = r
    # Tách original_id từ act_id (ví dụ: '19028650701_2' -> '19028650701')
    original_id = act_id.split("_")[0]
    
    # Ở đây ta không biết chắc original_id của ai nếu không gọi API, 
    # nhưng ta có thể đối chiếu chéo: nếu Nguyễn Minh Tú (ID=102) có strava_athlete_id là '42307924',
    # mà Lê Tuấn Anh (ID=123) có các hoạt động thuộc về tài khoản của Tú.
    pass

# Ta kiểm tra trực tiếp: tìm tất cả hoạt động của Lê Tuấn Anh (ID=123) xem có bao nhiêu hoạt động 
# thực chất thuộc về tài khoản Strava '42307924' (Nguyễn Minh Tú) hoặc tài khoản khác không phải của Lê Tuấn Anh.
# Để làm điều này, ta cần biết Lê Tuấn Anh liên kết từ khi nào.
# Hãy đếm xem có bao nhiêu hoạt động có athlete_id = 123 nhưng thực chất là của Tú.
# Từ kịch bản trước ta đã đếm được có 12 hoạt động của Tú bị gán cho Lê Tuấn Anh.

# Hãy kiểm tra xem có trường hợp tương tự với các VĐV khác không?
# Ví dụ: Có hoạt động nào trùng ID gốc nhưng khác athlete_id không?
# Vì ID gốc là duy nhất, nếu có hoạt động nào trong DB bị gán cho người A mà người B liên kết lại trùng thì đó là gán nhầm.

print("\nTìm các VĐV đã liên kết nhưng có 0 hoạt động:")
cur.execute("""
    SELECT id, full_name, strava_athlete_id 
    FROM athletes 
    WHERE strava_refresh_token IS NOT NULL AND id NOT IN (SELECT DISTINCT athlete_id FROM activities)
""")
for a in cur.fetchall():
    print(f"  VĐV: {a[1]} (ID={a[0]}, Strava ID={a[2]})")

conn.close()
