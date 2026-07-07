import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_backup():
    db_path = "SSO_HC_backup_v1.4.0_1783059852.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Check athlete info
    cur.execute("SELECT id, full_name, strava_name, is_active FROM athletes WHERE id = 51")
    ath = cur.fetchone()
    if ath:
        print(f"Athlete ID 51 | Name: {ath[1]} | Strava: {ath[2]} | Active: {ath[3]}")
    else:
        print("Athlete 51 not found!")
        
    # 2. Count activities and dates
    cur.execute("""
        SELECT COUNT(*), MIN(activity_date), MAX(activity_date)
        FROM activities
        WHERE athlete_id = 51
    """)
    total, min_date, max_date = cur.fetchone()
    print(f"Total activities in this backup for ID 51: {total} | Range: {min_date} to {max_date}")
    
    # 3. Check some activities
    cur.execute("""
        SELECT id, name, distance_km, activity_date, sport_type
        FROM activities
        WHERE athlete_id = 51
        ORDER BY activity_date DESC
        LIMIT 10
    """)
    for idx, r in enumerate(cur.fetchall()):
        print(f"  {idx+1}. ID: {r[0][:15]}... | Name: {r[1]} | Dist: {r[2]} km | Date: {r[3]} | Sport: {r[4]}")
        
    conn.close()

if __name__ == "__main__":
    check_backup()
