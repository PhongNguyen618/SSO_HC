import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_live():
    db_path = "SSO_HC.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. Check total activities in live DB
    cur.execute("SELECT COUNT(*) FROM activities")
    total_acts = cur.fetchone()[0]
    print(f"Total activities in live DB (SSO_HC.db): {total_acts}")
    
    # 2. Check total activities by event
    cur.execute("SELECT event_id, COUNT(*) FROM activities GROUP BY event_id")
    for r in cur.fetchall():
        print(f"  Event ID: {r[0]} | Count: {r[1]}")
        
    # 3. Check for Hoàng Thị Hà (ID 51 or any name matching 'Hà')
    cur.execute("SELECT id, full_name, strava_name FROM athletes WHERE full_name LIKE '%Hà%' OR full_name LIKE '%Ha%'")
    aths = cur.fetchall()
    print("\nMatching athletes in live DB:")
    for a in aths:
        cur.execute("SELECT COUNT(*), SUM(distance_km) FROM activities WHERE athlete_id = ?", (a[0],))
        cnt, dist = cur.fetchone()
        dist_val = dist if dist else 0.0
        print(f"  ID: {a[0]} | Name: {a[1]} | Strava: {a[2]} | Activities Count: {cnt} | Dist: {dist_val:.2f} km")
        
    # 4. Check details of athlete 51 if exists
    cur.execute("SELECT id, full_name FROM athletes WHERE id = 51")
    a51 = cur.fetchone()
    if a51:
        cur.execute("SELECT COUNT(*), MIN(activity_date), MAX(activity_date) FROM activities WHERE athlete_id = 51")
        cnt, mind, maxd = cur.fetchone()
        print(f"\nAthlete 51 (Hoàng Thị Hà) in live DB:")
        print(f"  Activities Count: {cnt} | Range: {mind} to {maxd}")
        
    conn.close()

if __name__ == "__main__":
    check_live()
