import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_events():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    db_active = "SSO_HC.db"
    
    for name, db_path in [("BACKUP DB", db_backup), ("ACTIVE DB", db_active)]:
        print(f"\n==================== {name} ====================")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, is_active FROM competition_events")
            rows = cursor.fetchall()
            for r in rows:
                print(f"ID: {r[0]} | Title: {r[1]} | Active: {r[2]}")
            conn.close()
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    check_events()
