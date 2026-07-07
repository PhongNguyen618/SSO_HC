import sqlite3
import os

def check_ids():
    backup_db = "static/uploads/backups/SSO_HC_auto_v1.4.0_20260704_081714.db"
    live_db = "SSO_HC_backup_v1.4.0_1783161208.db"
    
    for db_path, db_name in [(backup_db, "BACKUP"), (live_db, "LIVE")]:
        print(f"\n==================== Database: {db_name} ({db_path}) ====================")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        for a_id in [3, 23, 25, 51]:
            cur.execute("SELECT id, full_name, strava_name, is_active FROM athletes WHERE id = ?", (a_id,))
            r = cur.fetchone()
            if r:
                # Count activities
                cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ?", (a_id,))
                count = cur.fetchone()[0]
                safe_name = r[1].encode('ascii', 'ignore').decode('ascii')
                safe_strava = r[2].encode('ascii', 'ignore').decode('ascii') if r[2] else "None"
                print(f"Athlete ID: {r[0]} | Name: {safe_name} | Strava: {safe_strava} | Active: {r[3]} | Activities: {count}")
            else:
                print(f"Athlete ID: {a_id} NOT FOUND!")
        conn.close()

if __name__ == "__main__":
    check_ids()
