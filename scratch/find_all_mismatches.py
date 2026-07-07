import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(backup_db)
cur = conn.cursor()

# Đếm số VĐV đã liên kết Strava (có strava_refresh_token)
cur.execute("SELECT COUNT(*) FROM athletes WHERE strava_refresh_token IS NOT NULL")
total_linked = cur.fetchone()[0]
print(f"Tổng số VĐV đã liên kết Strava trong backup: {total_linked}")

# Lấy danh sách VĐV đã liên kết
cur.execute("SELECT id, full_name, strava_athlete_id FROM athletes WHERE strava_refresh_token IS NOT NULL")
linked_athletes = cur.fetchall()

# Kiểm tra xem có trường hợp nào khác mà hoạt động có ID dạng số (API) 
# thuộc về VĐV A (chưa hoặc đã liên kết) nhưng ID gốc của hoạt động không khớp với strava_athlete_id của họ không?
# Thực tế, để biết hoạt động có bị gán nhầm không, ta có thể kiểm tra xem:
# Có hoạt động nào có ID dạng số (ví dụ: '19028650701_2') đang thuộc về VĐV X, 
# nhưng trong DB lại có một VĐV Y khác có strava_athlete_id trùng khớp với chủ sở hữu thực sự của hoạt động đó?
# Để tìm chủ sở hữu thực sự của hoạt động từ Strava ID:
# Trong các hoạt động cào Club/Scraper ngày xưa, hoặc API Club, Strava ID của người chạy được trả về dưới dạng `athlete_id` trong payload của Strava.
# Ta xem cấu trúc lưu trữ: khi đồng bộ Club, hệ thống lưu `athlete_name_raw`.
# Hãy kiểm tra xem trong bảng `activities` có hoạt động nào mà `athlete_id` (ID trong DB của ta) 
# có thông tin `strava_athlete_id` ở bảng `athletes` không khớp với tài khoản chạy.
# Tuy nhiên, cách trực tiếp nhất là tìm những hoạt động dạng số (API) có athlete_id = X, 
# nhưng athlete_name_raw của nó lại giống với tên hoặc tên hiển thị của VĐV Y.

# Hãy tìm các hoạt động có dạng số (độ dài ID < 30) mà tên thô (athlete_name_raw) khác biệt lớn với tên VĐV (full_name) được gán.
cur.execute("""
    SELECT act.id, act.athlete_id, a.full_name, act.athlete_name_raw, act.event_id, act.activity_date
    FROM activities act
    JOIN athletes a ON act.athlete_id = a.id
    WHERE length(act.id) < 30 AND act.athlete_name_raw IS NOT NULL
""")
acts = cur.fetchall()

print("\n=== CÁC HOẠT ĐỘNG CÓ DẤU HIỆU LỆCH TÊN VĐV ===")
potential_mismatches = 0
for act in acts:
    act_id, ath_id, full_name, raw_name, ev_id, act_date = act
    # Chuẩn hóa tên để so sánh
    fn_clean = "".join(full_name.lower().split())
    rn_clean = "".join(raw_name.lower().split())
    
    # Nếu tên thô (raw_name từ Strava) không chứa phần nào của tên thật VĐV trong hệ thống
    # Ví dụ: raw_name = 'Lê Tuấn Anh' mà full_name = 'Nguyễn Minh Tú'
    # Ta check xem các từ khóa chính có khớp không
    fn_parts = [p for p in full_name.lower().replace(",", " ").replace(".", " ").split() if len(p) > 1]
    rn_parts = [p for p in raw_name.lower().replace(",", " ").replace(".", " ").split() if len(p) > 1]
    
    # Tìm giao của 2 tập hợp từ
    intersection = set(fn_parts).intersection(set(rn_parts))
    
    # Nếu không có từ nào chung (ví dụ "Lê Tuấn Anh" vs "Nguyễn Minh Tú")
    if not intersection and len(fn_parts) > 0 and len(rn_parts) > 0:
        potential_mismatches += 1
        print(f"LỆCH: ID={act_id} | VĐV DB={full_name} (ID={ath_id}) | Tên Strava={raw_name} | Giải={ev_id} | Ngày={act_date}")

print(f"\nTổng số hoạt động có dấu hiệu lệch tên: {potential_mismatches}")

conn.close()
