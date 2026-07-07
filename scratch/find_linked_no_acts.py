import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def find_linked_athletes_no_activities():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # Tìm VĐV có token nhưng không có hoạt động nào từ ngày 16/06
    cur.execute("""
        SELECT a.id, a.full_name, a.strava_name, a.strava_athlete_id, a.strava_expires_at
        FROM athletes a
        WHERE a.strava_refresh_token IS NOT NULL
    """)
    linked_athletes = cur.fetchall()
    
    print(f"=== DANH SÁCH VĐV ĐÃ LIÊN KẾT TRONG FILE BACKUP MỚI ({len(linked_athletes)} người) ===")
    
    mismatch_athletes = []
    
    for ath in linked_athletes:
        aid, name, strava_name, strava_id, expires_at = ath
        
        # Đếm số hoạt động kể từ ngày 16/06/2026
        cur.execute("""
            SELECT COUNT(*) FROM activities 
            WHERE athlete_id = ? AND activity_date >= '2026-06-16'
        """, (aid,))
        count_api = cur.fetchone()[0]
        
        # Đếm số hoạt động cào web cũ (nếu có)
        cur.execute("""
            SELECT COUNT(*) FROM activities 
            WHERE athlete_id = ? AND length(id) == 64
        """, (aid,))
        count_club = cur.fetchone()[0]
        
        # Kiểm tra đăng ký giải
        cur.execute("SELECT event_id FROM competition_registrations WHERE athlete_id = ?", (aid,))
        regs = [r[0] for r in cur.fetchall()]
        
        print(f"ID={aid} | Tên: {name} (Strava: {strava_name}) | Đăng ký giải: {regs}")
        print(f"  - Số hoạt động (từ 16/06): {count_api} | Hoạt động cào web cũ: {count_club}")
        
        if count_api == 0:
            mismatch_athletes.append(ath)
            
    print(f"\n=> Có {len(mismatch_athletes)} VĐV đã liên kết nhưng có 0 hoạt động từ ngày 16/06.")
    conn.close()

if __name__ == "__main__":
    find_linked_athletes_no_activities()
