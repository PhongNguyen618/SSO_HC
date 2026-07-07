import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def diagnose_tuan_and_hung():
    db_file = "SSO_HC_backup_v1.4.0_1783345876.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # 1. Kiểm tra Trần Ngọc Anh Tuấn (ID=78 hoặc tìm theo tên)
    cur.execute("""
        SELECT id, full_name, strava_name, strava_refresh_token, strava_athlete_id
        FROM athletes 
        WHERE full_name LIKE '%Trần Ngọc Anh Tuấn%'
    """)
    tuan = cur.fetchone()
    print("=== THÔNG TIN TRẦN NGỌC ANH TUẤN ===")
    if tuan:
        print(f"ID: {tuan[0]} | Tên: '{tuan[1]}' | Tên Strava cấu hình: '{tuan[2]}' | Token: {tuan[3]} | Athlete ID: {tuan[4]}")
    else:
        print("Không tìm thấy Trần Ngọc Anh Tuấn!")
        
    # 2. Kiểm tra Võ Mạnh Hùng (Tìm theo tên)
    cur.execute("""
        SELECT id, full_name, strava_name, strava_refresh_token, strava_athlete_id
        FROM athletes 
        WHERE full_name LIKE '%Võ Mạnh Hùng%'
    """)
    hung = cur.fetchone()
    print("\n=== THÔNG TIN VÕ MẠNH HÙNG ===")
    if hung:
        print(f"ID: {hung[0]} | Tên: '{hung[1]}' | Tên Strava cấu hình: '{hung[2]}' | Token: {hung[3]} | Athlete ID: {hung[4]}")
    else:
        print("Không tìm thấy Võ Mạnh Hùng!")
        
    # 3. Xem danh sách hoạt động gần đây của Trần Ngọc Anh Tuấn
    if tuan:
        print(f"\n=== HOẠT ĐỘNG GẦN ĐÂY CỦA TRẦN NGỌC ANH TUẤN (ID={tuan[0]}) ===")
        cur.execute("""
            SELECT id, athlete_name_raw, distance_km, activity_date, sport_type
            FROM activities
            WHERE athlete_id = ?
            ORDER BY activity_date DESC
            LIMIT 5
        """, (tuan[0],))
        acts = cur.fetchall()
        for a in acts:
            print(f"Bài ID: {a[0]} | Tên Strava trên hoạt động: '{a[1]}' | Cự ly: {a[2]} km | Ngày: {a[3]}")
            
    conn.close()

if __name__ == "__main__":
    diagnose_tuan_and_hung()
