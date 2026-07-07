import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def inspect_athlete_51_event_2_activities():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # Lấy thông tin 10 hoạt động đầu tiên của Hà ở giải 2
    cur.execute("""
        SELECT id, athlete_id, event_id, athlete_name_raw, name, type, distance_km, activity_date, kcal_burned, is_suspicious, suspicion_reason
        FROM activities 
        WHERE athlete_id = 51 AND event_id = 2
        LIMIT 10
    """)
    rows = cur.fetchall()
    
    print("=== KIỂM TRA 10 HOẠT ĐỘNG GIẢI 2 CỦA HOÀNG THỊ HÀ ===")
    for r in rows:
        print(f"ID: {r[0]}")
        print(f"  Athlete ID: {r[1]} | Tên thô: {r[3]}")
        print(f"  Event ID: {r[2]} | Tên bài: {r[4]} | Kiểu: {r[5]}")
        print(f"  Cự ly: {r[6]} km | Ngày: {r[7]} | Calo: {r[8]}")
        print(f"  Nghi vấn: {r[9]} | Lý do: {r[10]}")
        print("-" * 50)
        
    # Kiểm tra tổng số hoạt động nghi vấn của Hà ở giải 2
    cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = 51 AND event_id = 2 AND is_suspicious = 1")
    susp_count = cur.fetchone()[0]
    print(f"\nSố hoạt động bị đánh dấu NGHI VẤN (bị ẩn khỏi BXH): {susp_count} / 63")
    
    # Kiểm tra xem ID của hoạt động có dạng API cá nhân (dài ngắn) hay dạng cào web (dài 64 ký tự)
    cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = 51 AND event_id = 2 AND length(id) == 64")
    club_count = cur.fetchone()[0]
    print(f"Số hoạt động từ nguồn CÀO WEB (Club scraper): {club_count} / 63")
    
    cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = 51 AND event_id = 2 AND length(id) != 64")
    api_count = cur.fetchone()[0]
    print(f"Số hoạt động từ nguồn API cá nhân: {api_count} / 63")

    conn.close()

if __name__ == "__main__":
    inspect_athlete_51_event_2_activities()
