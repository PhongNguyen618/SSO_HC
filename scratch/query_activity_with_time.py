import sqlite3
import sys

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

def check_activity_with_time():
    conn = sqlite3.connect("SSO_HC.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, athlete_name_raw, name, type, distance_km, activity_date, activity_time, sync_date, multiplier 
        FROM activities 
        WHERE activity_time IS NOT NULL AND activity_time != ''
        LIMIT 10
    """)
    rows = cursor.fetchall()
    print("Cac hoat dong co activity_time:")
    for row in rows:
        print(f"ID: {row[0][:8]}... | Athlete: {row[1]} | Name: {row[2]} | Date: {row[5]} | Time: {row[6]} | Sync: {row[7]} | Mult: {row[8]}")
    conn.close()

if __name__ == "__main__":
    check_activity_with_time()
