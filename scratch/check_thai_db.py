import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_thai_status():
    db_file = "SSO_HC_backup_v1.4.0_1783345876.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # 1. Tìm thông tin VĐV Lê Văn Thái
    cur.execute("""
        SELECT id, full_name, department, strava_name, strava_refresh_token, strava_access_token, strava_athlete_id
        FROM athletes 
        WHERE full_name LIKE '%Lê Văn Thái%'
    """)
    thai = cur.fetchone()
    print("=== THÔNG TIN VĐV LÊ VĂN THÁI ===")
    if not thai:
        print("Không tìm thấy VĐV Lê Văn Thái trong DB!")
        conn.close()
        return
        
    athlete_id, full_name, dept, strava_name, refresh_token, access_token, strava_id = thai
    print(f"ID: {athlete_id}")
    print(f"Tên đăng ký: {full_name}")
    print(f"Phòng ban: {dept}")
    print(f"Tên Strava: {strava_name}")
    print(f"OAuth ID: {strava_id}")
    print(f"Refresh Token: {refresh_token[:15] + '...' if refresh_token else 'NULL'}")
    print(f"Access Token: {access_token[:15] + '...' if access_token else 'NULL'}")
    
    # 2. Kiểm tra các giải đấu đã đăng ký
    cur.execute("""
        SELECT r.event_id, e.title, e.start_date, e.end_date
        FROM competition_registrations r
        JOIN competition_events e ON r.event_id = e.id
        WHERE r.athlete_id = ?
    """, (athlete_id,))
    regs = cur.fetchall()
    print("\n=== ĐĂNG KÝ GIẢI ĐẤU ===")
    for r in regs:
        print(f"Giải ID: {r[0]} | Tên giải: '{r[1]}' | Từ {r[2]} đến {r[3]}")
        
    # 3. Kiểm tra số lượng hoạt động trong DB của Thái
    cur.execute("""
        SELECT event_id, COUNT(*), MIN(activity_date), MAX(activity_date)
        FROM activities
        WHERE athlete_id = ?
        GROUP BY event_id
    """, (athlete_id,))
    acts = cur.fetchall()
    print("\n=== HOẠT ĐỘNG TRONG CƠ SỞ DỮ LIỆU ===")
    if not acts:
        print("Không có hoạt động nào trong DB cho Lê Văn Thái!")
    for a in acts:
        print(f"Giải ID: {a[0]} | Số bài chạy: {a[1]} | Ngày chạy: từ {a[2]} đến {a[3]}")
        
    # 4. Kiểm tra xem có ai trùng token với Thái không
    if refresh_token:
        cur.execute("""
            SELECT id, full_name, department 
            FROM athletes 
            WHERE strava_refresh_token = ? AND id != ?
        """, (refresh_token, athlete_id))
        conflicts = cur.fetchall()
        print("\n=== KIỂM TRA TRÙNG TOKEN ===")
        if conflicts:
            print("CẢNH BÁO: Lê Văn Thái đang bị TRÙNG TOKEN với:")
            for c in conflicts:
                print(f" - ID: {c[0]} | Tên: {c[1]} | Phòng: {c[2]}")
        else:
            print("Lê Văn Thái KHÔNG bị trùng token với ai trong DB.")
            
    conn.close()

if __name__ == "__main__":
    check_thai_status()
