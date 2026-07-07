import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def query_unlinked_mai():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    conn = sqlite3.connect(db_backup)
    cursor = conn.cursor()
    
    print("=== Search in Backup DB for Activities containing 'Mai' ===")
    cursor.execute("SELECT DISTINCT athlete_name_raw FROM activities WHERE athlete_name_raw LIKE '%Mai%'")
    names = cursor.fetchall()
    print(f"Distinct names in activities matching 'Mai': {names}")
    
    for name in names:
        raw_name = name[0]
        cursor.execute("SELECT COUNT(*), athlete_id FROM activities WHERE athlete_name_raw = ?", (raw_name,))
        cnt, ath_id = cursor.fetchone()
        print(f"  Name: {raw_name} -> count: {cnt}, athlete_id: {ath_id}")
        
    conn.close()

if __name__ == "__main__":
    query_unlinked_mai()
