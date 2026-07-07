import os
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def find_db_files():
    db_files = []
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".db"):
                db_files.append(os.path.join(root, f))
    return db_files

def check_backups():
    db_files = find_db_files()
    print(f"Found {len(db_files)} database files to scan:")
    for path in db_files:
        print(f"  Scanning: {path} (Size: {os.path.getsize(path)} bytes)")
        try:
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            
            # Check if tables exist
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='athletes'")
            if not cur.fetchone():
                print("    [Info] No 'athletes' table.")
                conn.close()
                continue
                
            # Find Hoàng Thị Hà ID
            cur.execute("SELECT id, full_name, strava_name, strava_refresh_token FROM athletes WHERE full_name LIKE '%Hoàng Thị Hà%'")
            athlete = cur.fetchone()
            if athlete:
                ath_id, full_name, strava_name, has_token = athlete[0], athlete[1], athlete[2], athlete[3] is not None
                
                # Check linked activities
                cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ?", (ath_id,))
                linked_count = cur.fetchone()[0]
                
                # Check unlinked activities matching strava_name
                unlinked_count = 0
                if strava_name:
                    for part in strava_name.split(","):
                        cleaned = part.strip()
                        if cleaned:
                            cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id IS NULL AND athlete_name_raw LIKE ?", (f"%{cleaned}%",))
                            unlinked_count += cur.fetchone()[0]
                
                print(f"    [FOUND] Athlete ID: {ath_id} | Name: {full_name} | Strava: {strava_name} | Has Token: {has_token}")
                print(f"            Linked activities: {linked_count} | Unlinked matching: {unlinked_count}")
                
                # If there are linked activities, let's print dates
                if linked_count > 0:
                    cur.execute("SELECT MIN(activity_date), MAX(activity_date) FROM activities WHERE athlete_id = ?", (ath_id,))
                    min_date, max_date = cur.fetchone()
                    print(f"            Dates: {min_date} to {max_date}")
            else:
                print("    [Info] 'Hoàng Thị Hà' not found in athletes table.")
            conn.close()
        except Exception as e:
            print(f"    [Error] Failed to scan {path}: {e}")

if __name__ == "__main__":
    check_backups()
