import sqlite3

def check_2025():
    db_path = "static/uploads/backups/SSO_HC_auto_v1.4.0_20260704_081714.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*), MIN(activity_date), MAX(activity_date) FROM activities")
    total, min_date, max_date = cur.fetchone()
    print(f"Total activities in backup: {total} | Range: {min_date} to {max_date}")
    
    cur.execute("SELECT COUNT(*) FROM activities WHERE activity_date LIKE '2025-%'")
    count_2025 = cur.fetchone()[0]
    print(f"Activities in 2025: {count_2025}")
    
    # Let's see some 2025 activities if they exist
    if count_2025 > 0:
        cur.execute("SELECT athlete_id, athlete_name_raw, name, activity_date FROM activities WHERE activity_date LIKE '2025-%' LIMIT 10")
        for r in cur.fetchall():
            print(f"  Athlete ID: {r[0]} | Name Raw: {r[1]} | Title: {r[2]} | Date: {r[3]}")
            
    conn.close()

if __name__ == "__main__":
    check_2025()
