import sqlite3
import os

def restore_all():
    backup_db = "static/uploads/backups/SSO_HC_auto_v1.4.0_20260704_081714.db"
    live_db = "SSO_HC_backup_v1.4.0_1783161208.db"
    
    if not os.path.exists(backup_db) or not os.path.exists(live_db):
        print("Missing database files for restoration.")
        return
        
    print(f"Reading athletes and activities from BACKUP: {backup_db}")
    conn_b = sqlite3.connect(backup_db)
    cur_b = conn_b.cursor()
    cur_b.execute("SELECT id, full_name, strava_name FROM athletes")
    backup_athletes = cur_b.fetchall()
    
    backup_data = {}
    for a_id, name, s_name in backup_athletes:
        cur_b.execute("SELECT * FROM activities WHERE athlete_id = ?", (a_id,))
        col_names = [desc[0] for desc in cur_b.description]
        rows = cur_b.fetchall()
        backup_data[a_id] = {
            "name": name,
            "strava_name": s_name,
            "activities": [dict(zip(col_names, r)) for r in rows]
        }
    conn_b.close()
    
    print(f"Connecting to LIVE database: {live_db}")
    conn_l = sqlite3.connect(live_db)
    cur_l = conn_l.cursor()
    
    cur_l.execute("SELECT id, full_name FROM athletes")
    live_athletes = cur_l.fetchall()
    live_name_map = {ath[1].strip().lower(): ath[0] for ath in live_athletes}
    
    total_restored = 0
    
    for old_id, info in backup_data.items():
        name = info["name"]
        acts = info["activities"]
        if not acts:
            continue
            
        norm_name = name.strip().lower()
        if norm_name not in live_name_map:
            safe_name = name.encode('ascii', 'ignore').decode('ascii')
            print(f"[Warning] Athlete '{safe_name}' (Old ID: {old_id}) not found in live DB by name match.")
            continue
            
        new_id = live_name_map[norm_name]
        safe_name = name.encode('ascii', 'ignore').decode('ascii')
        print(f"Restoring activities for '{safe_name}' (Old ID: {old_id} -> Live ID: {new_id}). Backup has {len(acts)} activities.")
        
        inserted = 0
        skipped = 0
        
        for act in acts:
            act["athlete_id"] = new_id
            
            cur_l.execute("SELECT id FROM activities WHERE id = ?", (act["id"],))
            if cur_l.fetchone():
                skipped += 1
                continue
                
            col_names = list(act.keys())
            placeholders = ", ".join(["?"] * len(col_names))
            columns = ", ".join(col_names)
            query = f"INSERT INTO activities ({columns}) VALUES ({placeholders})"
            
            cur_l.execute(query, tuple(act.values()))
            inserted += 1
            total_restored += 1
            
        print(f"    - Restored: {inserted} | Skipped: {skipped}")
        
    conn_l.commit()
    conn_l.close()
    print(f"\n[OK] Restoration finished. Total activities restored across all athletes: {total_restored}")

if __name__ == "__main__":
    restore_all()
