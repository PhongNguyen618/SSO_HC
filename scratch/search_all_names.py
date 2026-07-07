import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def print_all_names():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    conn = sqlite3.connect(db_backup)
    cursor = conn.cursor()
    
    print("=== Distinct athlete_name_raw in backup DB ===")
    cursor.execute("SELECT DISTINCT athlete_name_raw FROM activities ORDER BY athlete_name_raw")
    names = [n[0] for n in cursor.fetchall() if n[0]]
    for name in names:
        print(name)
        
    conn.close()

if __name__ == "__main__":
    print_all_names()
