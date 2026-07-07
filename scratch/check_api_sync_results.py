import sqlite3

def check_sync():
    db_path = "SSO_HC.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Lấy danh sách VĐV có liên kết Strava (có strava_refresh_token)
    cur.execute("""
        SELECT id, full_name, strava_name, strava_athlete_id
        FROM athletes
        WHERE strava_refresh_token IS NOT NULL AND strava_refresh_token != ''
    """)
    linked_athletes = cur.fetchall()
    print(f"Total linked athletes: {len(linked_athletes)}")
    
    # 2. Với mỗi VĐV, xem họ đăng ký giải nào và số hoạt động trong giải đó kể từ ngày 16/06/2026
    for ath_id, name, s_name, s_id in linked_athletes:
        safe_name = name.encode('ascii', 'ignore').decode('ascii')
        print(f"\nAthlete ID: {ath_id} | Name: {safe_name} | Strava Name: {s_name} | Strava ID: {s_id}")
        
        # Xem đăng ký giải
        cur.execute("SELECT event_id FROM competition_registrations WHERE athlete_id = ?", (ath_id,))
        regs = [r[0] for r in cur.fetchall()]
        print(f"  Registered Event IDs: {regs}")
        
        # Xem hoạt động sau ngày 16/06/2026 cho từng giải
        for ev_id in regs:
            cur.execute("""
                SELECT COUNT(*), SUM(distance_km)
                FROM activities
                WHERE athlete_id = ? AND event_id = ? AND activity_date >= '2026-06-16'
            """, (ath_id, ev_id))
            cnt, dist = cur.fetchone()
            dist_val = dist if dist else 0.0
            print(f"    Event ID: {ev_id} | Activities >= 16/06: {cnt} | Dist: {dist_val:.2f} km")
            
            # Xem hoạt động trước ngày 16/06/2026
            cur.execute("""
                SELECT COUNT(*), SUM(distance_km)
                FROM activities
                WHERE athlete_id = ? AND event_id = ? AND activity_date < '2026-06-16'
            """, (ath_id, ev_id))
            cnt_old, dist_old = cur.fetchone()
            dist_old_val = dist_old if dist_old else 0.0
            print(f"    Event ID: {ev_id} | Activities < 16/06: {cnt_old} | Dist: {dist_old_val:.2f} km")
            
    conn.close()

if __name__ == "__main__":
    check_sync()
