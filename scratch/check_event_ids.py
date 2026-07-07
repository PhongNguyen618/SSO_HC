import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_competition_event_ids():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    cur.execute("SELECT id, title, start_date, end_date, is_active FROM competition_events")
    rows = cur.fetchall()
    
    print("=== DANH SÁCH GIẢI ĐẤU VÀ ID TRONG CƠ SỞ DỮ LIỆU LIVE ===")
    for r in rows:
        print(f"ID: {r[0]} | Tên giải: '{r[1]}' | Bắt đầu: {r[2]} | Kết thúc: {r[3]} | Hoạt động: {r[4]}")
        
    conn.close()

if __name__ == "__main__":
    check_competition_event_ids()
