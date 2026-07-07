import os
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_all_dbs():
    db_files = []
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".db"):
                db_files.append(os.path.join(root, f))
                
    for path in db_files:
        if os.path.getsize(path) == 0:
            continue
        print(f"\n==================== File: {path} ====================")
        try:
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            
            # Check if tables exist
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activities'")
            if not cur.fetchone():
                print("No activities table.")
                conn.close()
                continue
                
            cur.execute("SELECT id, name, distance_km, activity_date, sport_type FROM activities WHERE athlete_id = 51 ORDER BY activity_date")
            rows = cur.fetchall()
            print(f"Total activities for athlete ID 51: {len(rows)}")
            for idx, r in enumerate(rows[:5]):
                print(f"  {idx+1}. ID: {r[0][:15]}... | Name: {r[1]} | Dist: {r[2]} km | Date: {r[3]} | Sport: {r[4]}")
            if len(rows) > 5:
                print("  ...")
                for idx, r in enumerate(rows[-5:]):
                    print(f"  {len(rows)-4+idx}. ID: {r[0][:15]}... | Name: {r[1]} | Dist: {r[2]} km | Date: {r[3]} | Sport: {r[4]}")
            conn.close()
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    check_all_dbs()
