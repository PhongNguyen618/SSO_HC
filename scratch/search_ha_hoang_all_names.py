import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def search_names():
    db_path = "SSO_HC_backup_v1.4.0_1783161208.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Let's search all distinct athlete_name_raw in 2025 containing "Hà" or "Ha" or "Hoàng" or "Hoang"
    print("=== Distinct athlete_name_raw in 2025 containing 'Hà', 'Ha', 'Hoàng', 'Hoang' ===")
    cur.execute("""
        SELECT DISTINCT athlete_name_raw, COUNT(*), MIN(activity_date), MAX(activity_date)
        FROM activities 
        WHERE (athlete_name_raw LIKE '%Hà%' OR athlete_name_raw LIKE '%Ha%' OR athlete_name_raw LIKE '%Hoàng%' OR athlete_name_raw LIKE '%Hoang%')
          AND activity_date LIKE '2025-%'
        GROUP BY athlete_name_raw
    """)
    rows = cur.fetchall()
    for r in rows:
        print(f"Name: {r[0]} | Count: {r[1]} | Dates: {r[2]} to {r[3]}")
        
    print("\n=== Checking if she was registered under another ID in 2025 ===")
    # Let's search for "Hoàng Thị Hà" or "Ha Hoang" or "Ha H" in the athletes table
    cur.execute("SELECT id, full_name, strava_name, is_active FROM athletes WHERE full_name LIKE '%Hà%' OR full_name LIKE '%Ha%'")
    athletes = cur.fetchall()
    for a in athletes:
        print(f"Athlete ID: {a[0]} | Name: {a[1]} | Strava Name: {a[2]} | Active: {a[3]}")
        
    conn.close()

if __name__ == "__main__":
    search_names()
