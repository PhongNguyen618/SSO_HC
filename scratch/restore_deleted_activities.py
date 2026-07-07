import sqlite3
import os

def restore_activities():
    backup_db = "static/uploads/backups/SSO_HC_auto_v1.4.0_20260704_081714.db"
    
    if not os.path.exists(backup_db):
        backups_dir = "static/uploads/backups"
        if os.path.exists(backups_dir):
            files = sorted([f for f in os.listdir(backups_dir) if f.endswith(".db")])
            if files:
                backup_db = os.path.join(backups_dir, files[-1])
                print(f"Using latest auto backup found: {backup_db}")
            else:
                print("No auto backup DB files found.")
                return
        else:
            print("No auto backup directory found.")
            return

    target_dbs = ["SSO_HC.db", "SSO_HC_backup_v1.4.0_1783161208.db"]
    
    print(f"Reading activities for Athlete ID 51 from {backup_db}...")
    conn_b = sqlite3.connect(backup_db)
    cur_b = conn_b.cursor()
    
    cur_b.execute("SELECT * FROM activities WHERE athlete_id = 51")
    col_names = [description[0] for description in cur_b.description]
    rows = cur_b.fetchall()
    conn_b.close()
    
    print(f"Found {len(rows)} activities to restore.")
    if not rows:
        print("No activities found for athlete ID 51 in backup.")
        return

    for target in target_dbs:
        if not os.path.exists(target):
            print(f"Target DB {target} does not exist. Skipping.")
            continue
            
        print(f"Restoring to {target}...")
        conn_t = sqlite3.connect(target)
        cur_t = conn_t.cursor()
        
        inserted = 0
        skipped = 0
        for r in rows:
            act_data = dict(zip(col_names, r))
            
            cur_t.execute("SELECT id FROM activities WHERE id = ?", (act_data["id"],))
            if cur_t.fetchone():
                skipped += 1
                continue
                
            placeholders = ", ".join(["?"] * len(col_names))
            columns = ", ".join(col_names)
            query = f"INSERT INTO activities ({columns}) VALUES ({placeholders})"
            
            cur_t.execute(query, tuple(r))
            inserted += 1
            
        conn_t.commit()
        conn_t.close()
        print(f"  Result for {target}: Restored {inserted} activities, skipped {skipped} duplicates.")

if __name__ == "__main__":
    restore_activities()
