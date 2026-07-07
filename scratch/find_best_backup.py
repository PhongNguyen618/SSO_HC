import os
import sqlite3

def find_best_backup():
    # Find all .db files
    db_files = []
    # Check root
    for f in os.listdir("."):
        if f.endswith(".db") and f != "SSO_HC.db" and f != "test_sync_grace.db":
            db_files.append(f)
    # Check backups folder
    backups_dir = os.path.join("static", "uploads", "backups")
    if os.path.exists(backups_dir):
        for f in os.listdir(backups_dir):
            if f.endswith(".db"):
                db_files.append(os.path.join(backups_dir, f))
                
    print("Found backups:")
    best_db = None
    max_acts = -1
    
    for db_path in db_files:
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM activities")
            count = cur.fetchone()[0]
            # Also check count for athlete 51 specifically
            cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = 51")
            count_51 = cur.fetchone()[0]
            print(f"  {db_path} | Total activities: {count} | Athlete 51 activities: {count_51}")
            
            if count_51 > max_acts:
                max_acts = count_51
                best_db = db_path
            conn.close()
        except Exception as e:
            print(f"  Error reading {db_path}: {e}")
            
    print(f"\nBest backup database (highest count for Athlete 51): {best_db} with {max_acts} activities.")

if __name__ == "__main__":
    find_best_backup()
