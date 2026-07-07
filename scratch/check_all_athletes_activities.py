import sqlite3
import os

def compare_athletes():
    backup_db = "static/uploads/backups/SSO_HC_auto_v1.4.0_20260704_081714.db"
    live_db = "SSO_HC_backup_v1.4.0_1783161208.db"
    
    if not os.path.exists(backup_db) or not os.path.exists(live_db):
        print("Missing database files for comparison.")
        return
        
    print("Comparing activities count per athlete between backup and live DB:")
    
    conn_b = sqlite3.connect(backup_db)
    cur_b = conn_b.cursor()
    cur_b.execute("SELECT id, full_name, strava_name FROM athletes")
    athletes = cur_b.fetchall()
    
    backup_counts = {}
    for a_id, name, s_name in athletes:
        cur_b.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ?", (a_id,))
        count = cur_b.fetchone()[0]
        backup_counts[a_id] = (name, s_name, count)
    conn_b.close()
    
    conn_l = sqlite3.connect(live_db)
    cur_l = conn_l.cursor()
    
    live_counts = {}
    for a_id in backup_counts.keys():
        cur_l.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ?", (a_id,))
        count = cur_l.fetchone()[0]
        live_counts[a_id] = count
    conn_l.close()
    
    diff_found = False
    for a_id, (name, s_name, b_count) in backup_counts.items():
        l_count = live_counts.get(a_id, 0)
        if b_count > l_count:
            diff_found = True
            safe_name = name.encode('ascii', 'ignore').decode('ascii')
            safe_sname = str(s_name).encode('ascii', 'ignore').decode('ascii') if s_name else "None"
            print(f"Athlete ID: {a_id} | Name: {safe_name} (Strava: {safe_sname})")
            print(f"  Backup count: {b_count} | Live count: {l_count} (Lost: {b_count - l_count})")
            
    if not diff_found:
        print("No athletes have lost activities between backup and live DBs.")

if __name__ == "__main__":
    compare_athletes()
