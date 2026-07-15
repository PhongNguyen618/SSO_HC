"""Check all SQLite database files in the directory for departments containing 'Vĩnh Long'."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3

files = [f for f in os.listdir('.') if f.endswith('.db')]
print(f"Found {len(files)} database files:")

for db_file in files:
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Check if table 'athletes' exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='athletes'")
        if not cursor.fetchone():
            conn.close()
            continue
            
        cursor.execute("SELECT department, COUNT(*) FROM athletes GROUP BY department")
        rows = cursor.fetchall()
        
        vinh_long_depts = []
        for dept, count in rows:
            if dept and ("vĩnh long" in dept.lower() or "vinh long" in dept.lower()):
                vinh_long_depts.append((dept, count))
                
        if vinh_long_depts:
            print(f"\n📂 Database: {db_file}")
            for dept, count in vinh_long_depts:
                print(f"  - '{dept}' (Length: {len(dept)}): {count} athletes")
                # Print hex
                print(f"    Hex: {dept.encode('utf-8').hex()}")
                
        conn.close()
    except Exception as e:
        print(f"  Error reading {db_file}: {e}")
