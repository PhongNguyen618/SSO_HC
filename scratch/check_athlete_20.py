import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_athlete_20():
    db_path = "SSO_HC_backup_v1.4.0_1783161208.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT id, full_name, strava_name, department, is_active FROM athletes WHERE id = 20")
    r = cur.fetchone()
    if r:
        print(f"Athlete ID 20 | Name: {r[1]} | Strava Name: {r[2]} | Dept: {r[3]} | Active: {r[4]}")
    else:
        print("Athlete ID 20 not found!")
        
    conn.close()

if __name__ == "__main__":
    check_athlete_20()
