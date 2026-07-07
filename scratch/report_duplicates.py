import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def report_duplicate_tokens_with_departments():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # Lấy các refresh token bị trùng
    cur.execute("""
        SELECT strava_refresh_token, COUNT(*) 
        FROM athletes 
        WHERE strava_refresh_token IS NOT NULL 
        GROUP BY strava_refresh_token 
        HAVING COUNT(*) > 1
    """)
    dup_tokens = [r[0] for r in cur.fetchall()]
    
    if not dup_tokens:
        print("Không tìm thấy VĐV nào bị trùng lặp token.")
        conn.close()
        return
        
    print("=========================================================================")
    print(" DANH SÁCH CÁC VĐV BỊ TRÙNG LẶP TOKEN VÀ PHÒNG BAN (CẦN LIÊN KẾT LẠI)")
    print("=========================================================================")
    
    group_num = 1
    for token in dup_tokens:
        cur.execute("""
            SELECT id, full_name, department, strava_name, strava_athlete_id
            FROM athletes 
            WHERE strava_refresh_token = ?
        """, (token,))
        users = cur.fetchall()
        
        print(f"\n[Nhóm Trùng {group_num}] (Dùng chung token có đuôi: ...{token[-10:]})")
        print(f"{'ID':<6} | {'Họ và Tên':<25} | {'Phòng Ban':<20} | {'Tên hiển thị Strava':<30}")
        print("-" * 90)
        for uid, name, dept, s_name, s_id in users:
            print(f"{uid:<6} | {name:<25} | {dept:<20} | {s_name:<30}")
        group_num += 1
        
    conn.close()

if __name__ == "__main__":
    report_duplicate_tokens_with_departments()
