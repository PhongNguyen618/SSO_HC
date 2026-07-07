import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_thai_activities_details():
    db_file = "SSO_HC_backup_v1.4.0_1783059852.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # Lấy thông tin chi tiết giải đấu của 195 hoạt động của Thái
    cur.execute("""
        SELECT event_id, COUNT(*), MIN(activity_date), MAX(activity_date)
        FROM activities
        WHERE athlete_id = 44
        GROUP BY event_id
    """)
    rows = cur.fetchall()
    print("=== THÔNG TIN 195 HOẠT ĐỘNG CỦA LÊ VĂN THÁI TRONG BACKUP GỐC ===")
    for r in rows:
        print(f"Giải ID: {r[0]} | Số bài: {r[1]} | Từ {r[2]} đến {r[3]}")
        
    conn.close()

if __name__ == "__main__":
    check_thai_activities_details()
