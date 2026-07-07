import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_athlete_51_registrations():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # Kiểm tra thông tin VĐV
    cur.execute("SELECT id, full_name, department, is_active FROM athletes WHERE id = 51")
    athlete = cur.fetchone()
    print("=== THÔNG TIN VĐV HOÀNG THỊ HÀ ===")
    if athlete:
        print(f"ID: {athlete[0]} | Tên: {athlete[1]} | Phòng ban: {athlete[2]} | Trạng thái: {athlete[3]}")
    else:
        print("Không tìm thấy VĐV ID 51!")
        
    # Kiểm tra các giải đấu đã đăng ký trong DB live
    cur.execute("""
        SELECT r.event_id, e.title, e.is_active, e.start_date, e.end_date
        FROM competition_registrations r
        JOIN competition_events e ON r.event_id = e.id
        WHERE r.athlete_id = 51
    """)
    regs = cur.fetchall()
    print("\n=== CÁC GIẢI ĐẤU HOÀNG THỊ HÀ ĐÃ ĐĂNG KÝ TRONG DB ===")
    for r in regs:
        print(f"Giải ID: {r[0]} | Tên giải: '{r[1]}' | Trạng thái giải: {r[2]} | Thời gian: {r[3]} đến {r[4]}")
        
    # Đếm số lượng hoạt động của Hà ở các giải đấu khác nhau
    cur.execute("""
        SELECT event_id, COUNT(*) 
        FROM activities 
        WHERE athlete_id = 51 
        GROUP BY event_id
    """)
    acts = cur.fetchall()
    print("\n=== THỐNG KÊ HOẠT ĐỘNG CỦA HÀ TRONG DB ===")
    for a in acts:
        print(f"Giải ID: {a[0]} | Số hoạt động: {a[1]}")
        
    conn.close()

if __name__ == "__main__":
    check_athlete_51_registrations()
