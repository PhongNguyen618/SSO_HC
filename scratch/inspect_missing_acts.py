import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def inspect_missing_activities_source():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    conn = sqlite3.connect(db_backup)
    cur = conn.cursor()
    
    missing_ids = [1, 2, 9, 15, 16, 17, 22, 27, 32, 44, 78]
    
    print("=== KIỂM TRA TRƯỜNG TÊN VĐV TRONG HOẠT ĐỘNG CỦA FILE BACKUP GỐC ===")
    for ath_id in missing_ids:
        # Lấy tên VĐV từ bảng athletes
        cur.execute("SELECT full_name FROM athletes WHERE id = ?", (ath_id,))
        ath_name = cur.fetchone()[0]
        
        # Lấy thông tin 1 hoạt động tiêu biểu của VĐV này trong bảng activities của backup
        cur.execute("""
            SELECT id, athlete_id, athlete_name_raw
            FROM activities
            WHERE athlete_id = ? AND activity_date < '2026-06-16' AND event_id = 1
            LIMIT 1
        """, (ath_id,))
        act = cur.fetchone()
        
        if act:
            print(f"VĐV ID {ath_id} ('{ath_name}'):")
            print(f"  Hoạt động ID: {act[0]}")
            print(f"  athlete_id trong bảng activities: {act[1]}")
            print(f"  athlete_name_raw                : '{act[2]}'")
        else:
            print(f"VĐV ID {ath_id} ('{ath_name}'): KHÔNG CÓ hoạt động nào trong bảng activities của backup!")
        print("-" * 50)
        
    conn.close()

if __name__ == "__main__":
    inspect_missing_activities_source()
