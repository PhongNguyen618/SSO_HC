import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_unlinked_athletes():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # Lấy các VĐV hoạt động nhưng không có token
    cur.execute("""
        SELECT id, full_name, department, strava_name, is_active 
        FROM athletes 
        WHERE strava_refresh_token IS NULL AND is_active = 1
    """)
    rows = cur.fetchall()
    
    print(f"=== DANH SÁCH VĐV CHƯA LIÊN KẾT (HOẶC ĐÃ HỦY LIÊN KẾT) - TỔNG CỘNG {len(rows)} NGƯỜI ===")
    for r in rows[:20]: # In ra 20 người đầu tiên
        print(f"ID: {r[0]:<4} | Tên: {r[1]:<25} | Phòng: {r[2]:<20} | Strava Name: {r[3]}")
    
    # Kiểm tra riêng trạng thái của Hoàng Thị Hà (ID=51)
    cur.execute("SELECT id, full_name, strava_refresh_token, strava_access_token FROM athletes WHERE id = 51")
    ha = cur.fetchone()
    print("\n=== TRẠNG THÁI HIỆN TẠI CỦA HOÀNG THỊ HÀ TRONG DB GỬI ===")
    if ha:
        print(f"ID: {ha[0]} | Tên: {ha[1]}")
        print(f"Refresh Token: {ha[2]}")
        print(f"Access Token: {ha[3]}")
        
    conn.close()

if __name__ == "__main__":
    check_unlinked_athletes()
