import sqlite3

def check_dates():
    db_path = "static/uploads/backups/SSO_HC_auto_v1.4.0_20260704_081714.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT activity_date, COUNT(*)
        FROM activities
        WHERE athlete_id = 51
        GROUP BY activity_date
        ORDER BY activity_date
    """)
    rows = cur.fetchall()
    print("Distinct dates for Athlete ID 51 in BACKUP:")
    for r in rows:
        print(f"  Date: {r[0]} | Count: {r[1]}")
    conn.close()

if __name__ == "__main__":
    check_dates()
