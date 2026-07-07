import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def list_depts():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    conn = sqlite3.connect(db_backup)
    cursor = conn.cursor()
    
    print("=== Distinct departments in backup DB ===")
    cursor.execute("SELECT DISTINCT department FROM athletes ORDER BY department")
    depts = cursor.fetchall()
    for d in depts:
        print(d[0])
        
    conn.close()

if __name__ == "__main__":
    list_depts()
