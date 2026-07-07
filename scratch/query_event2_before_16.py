import sqlite3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_db_dates():
    conn = sqlite3.connect("SSO_HC_backup_v1.4.0_1783059852.db")
    cursor = conn.cursor()
    
    print("=== ACTIVITIES BEFORE 2026-06-16 FOR EVENT 2 ===")
    cursor.execute("""
        SELECT id, athlete_name_raw, name, activity_date, activity_time, distance_km 
        FROM activities 
        WHERE event_id = 2 AND activity_date < '2026-06-16' 
        ORDER BY activity_date ASC
    """)
    acts = cursor.fetchall()
    print(f"Total: {len(acts)} activities")
    for act in acts[:20]:
        id_type = "API" if not len(act[0]) == 64 else "Club/Scrape"
        print(f"ID: {act[0]} ({id_type}), Name: {act[1]}, ActName: {act[2]}, Date: {act[3]}, Time: {act[4]}, Dist: {act[5]} km")
        
    conn.close()

if __name__ == "__main__":
    check_db_dates()
