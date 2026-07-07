import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def search_2026_activities():
    db_path = "SSO_HC_backup_v1.4.0_1783161208.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print("=== Searching distinct athlete_name_raw in 2026 after 2026-06-16 ===")
    cur.execute("""
        SELECT DISTINCT athlete_name_raw, COUNT(*), MIN(activity_date), MAX(activity_date)
        FROM activities 
        WHERE activity_date >= '2026-06-16'
        GROUP BY athlete_name_raw
        ORDER BY COUNT(*) DESC
    """)
    for r in cur.fetchall():
        print(f"Name: {r[0]} | Count: {r[1]} | Dates: {r[2]} to {r[3]}")
        
    print("\n=== Searching activities specifically matching 'Ha H.' or 'Ha Hoang' after 2026-06-16 ===")
    cur.execute("""
        SELECT id, athlete_id, athlete_name_raw, name, distance_km, activity_date, sport_type
        FROM activities 
        WHERE (athlete_name_raw LIKE '%Ha H%' OR athlete_name_raw LIKE '%Ha Hoang%' OR athlete_name_raw = 'Ha H.' OR athlete_name_raw = 'Ha Hoang')
          AND activity_date >= '2026-06-16'
        ORDER BY activity_date
    """)
    rows = cur.fetchall()
    print(f"Total matching activities: {len(rows)}")
    for idx, r in enumerate(rows):
        print(f"  {idx+1}. ID: {r[0][:15]}... | AthID: {r[1]} | Name Raw: {r[2]} | Title: {r[3]} | Dist: {r[4]} km | Date: {r[5]} | Sport: {r[6]}")
        
    conn.close()

if __name__ == "__main__":
    search_2026_activities()
