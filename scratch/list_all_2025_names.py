import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def list_all_2025():
    db_path = "SSO_HC_backup_v1.4.0_1783161208.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT athlete_name_raw, COUNT(*), MIN(activity_date), MAX(activity_date)
        FROM activities 
        WHERE activity_date LIKE '2025-%'
        GROUP BY athlete_name_raw
        ORDER BY COUNT(*) DESC
    """)
    rows = cur.fetchall()
    print("=== All distinct athlete_name_raw in 2025 ===")
    for r in rows:
        print(f"Name: {r[0]} | Count: {r[1]} | Dates: {r[2]} to {r[3]}")
        
    conn.close()

if __name__ == "__main__":
    list_all_2025()
