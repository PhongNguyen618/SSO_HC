import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def query_hoang_h():
    db_path = "SSO_HC_backup_v1.4.0_1783161208.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT id, athlete_id, athlete_name_raw, name, distance_km, activity_date FROM activities WHERE athlete_name_raw = 'Hoàng H.' ORDER BY activity_date")
    rows = cur.fetchall()
    print(f"Total activities for 'Hoàng H.': {len(rows)}")
    for idx, r in enumerate(rows):
        print(f"  {idx+1}. ID: {r[0][:15]}... | Athlete ID: {r[1]} | Name Raw: {r[2]} | Title: {r[3]} | Dist: {r[4]} km | Date: {r[5]}")
        
    conn.close()

if __name__ == "__main__":
    query_hoang_h()
