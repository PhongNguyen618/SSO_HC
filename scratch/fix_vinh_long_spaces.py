"""Simulate or apply TRIM on department column for all athletes in the database."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3

db_files = ["SSO_HC.db", "SSO_HC_backup_v1.4.0_1784021166.db"]

for db_file in db_files:
    if not os.path.exists(db_file):
        continue
    print(f"\nProcessing database: {db_file}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Find all athletes where department has trailing or leading spaces
    cursor.execute("SELECT id, full_name, department FROM athletes WHERE department != trim(department)")
    rows = cursor.fetchall()
    
    if rows:
        print(f"  Found {len(rows)} athletes with leading/trailing spaces in department:")
        for r in rows:
            print(f"    * ID: {r[0]}, Name: {r[1]}, Current Dept: '{r[2]}' -> Will be trimmed to: '{r[2].strip()}'")
            
        # Apply update
        cursor.execute("UPDATE athletes SET department = trim(department)")
        conn.commit()
        print("  ✅ Successfully applied TRIM to all department fields!")
    else:
        print("  No athletes found with leading/trailing spaces in department.")
        
    conn.close()
