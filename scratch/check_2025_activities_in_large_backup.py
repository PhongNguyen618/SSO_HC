import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_2025():
    db_path = "SSO_HC_backup_v1.4.0_1783161208.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*), MIN(activity_date), MAX(activity_date) FROM activities")
    total, min_date, max_date = cur.fetchone()
    print(f"Total activities in large backup: {total} | Range: {min_date} to {max_date}")
    
    cur.execute("SELECT COUNT(*) FROM activities WHERE activity_date LIKE '2025-%'")
    count_2025 = cur.fetchone()[0]
    print(f"Activities in 2025: {count_2025}")
    
    # Check count specifically for athlete_id = 51 (Hoàng Thị Hà)
    cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = 51")
    count_51_linked = cur.fetchone()[0]
    
    # Also search for activities matching her strava_name "Ha H." or "Ha Hoang" in 2025 (either linked or unlinked!)
    cur.execute("SELECT COUNT(*) FROM activities WHERE (athlete_id = 51 OR athlete_name_raw LIKE '%Ha H%' OR athlete_name_raw LIKE '%Ha Hoang%') AND activity_date LIKE '2025-%'")
    count_51_2025 = cur.fetchone()[0]
    print(f"Hoàng Thị Hà activities in 2025: {count_51_2025}")
    
    if count_51_2025 > 0:
        cur.execute("""
            SELECT id, athlete_id, athlete_name_raw, name, distance_km, activity_date 
            FROM activities 
            WHERE (athlete_id = 51 OR athlete_name_raw LIKE '%Ha H%' OR athlete_name_raw LIKE '%Ha Hoang%') 
              AND activity_date LIKE '2025-%'
            ORDER BY activity_date
        """)
        rows = cur.fetchall()
        for idx, r in enumerate(rows[:10]):
            print(f"  {idx+1}. ID: {r[0][:15]}... | AthID: {r[1]} | Name Raw: {r[2]} | Title: {r[3]} | Dist: {r[4]} km | Date: {r[5]}")
            
    conn.close()

if __name__ == "__main__":
    check_2025()
