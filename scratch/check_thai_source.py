import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_thai_in_source_backup():
    db_file = "SSO_HC_backup_v1.4.0_1783059852.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # 1. Tìm Lê Văn Thái trong file backup gốc
    cur.execute("SELECT id, full_name, strava_name FROM athletes WHERE full_name LIKE '%Thái%'")
    rows = cur.fetchall()
    print("=== DANH SÁCH VĐV TÊN 'THÁI' TRONG FILE BACKUP GỐC ===")
    for r in rows:
        print(f"ID: {r[0]} | Tên đầy đủ: '{r[1]}' | Tên Strava: '{r[2]}'")
        
    # Đếm số hoạt động của các VĐV tên Thái trong file backup gốc
    for r in rows:
        ath_id = r[0]
        cur.execute("SELECT COUNT(*), MIN(activity_date), MAX(activity_date) FROM activities WHERE athlete_id = ?", (ath_id,))
        count, min_d, max_d = cur.fetchone()
        print(f" -> VĐV ID {ath_id} ({r[1]}): Có {count} hoạt động (từ {min_d} đến {max_d})")
        
    conn.close()

if __name__ == "__main__":
    check_thai_in_source_backup()
