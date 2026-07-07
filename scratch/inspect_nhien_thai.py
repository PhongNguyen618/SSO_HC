import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def inspect_nhien_thai():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, full_name, strava_name, strava_athlete_id, strava_access_token, strava_refresh_token, strava_expires_at
        FROM athletes 
        WHERE id IN (28, 44)
    """)
    rows = cur.fetchall()
    print("=== THÔNG TIN CHI TIẾT NHIÊN & THÁI ===")
    for r in rows:
        print(f"ID={r[0]}")
        print(f"  Tên VĐV: {r[1]}")
        print(f"  Tên hiển thị Strava: {r[2]}")
        print(f"  Strava Athlete ID: {r[3]}")
        print(f"  Access Token: {r[4][:15]}..." if r[5] else "  Access Token: None")
        print(f"  Refresh Token: {r[5][:15]}..." if r[5] else "  Refresh Token: None")
        print(f"  Expires At: {r[6]}")
        
    conn.close()

if __name__ == "__main__":
    inspect_nhien_thai()
