"""Find the 2 athletes in the duplicate department with trailing space."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3

db_file = "SSO_HC_backup_v1.4.0_1784021166.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Find the ones with trailing space
cursor.execute("SELECT id, full_name, department, strava_name, is_active FROM athletes WHERE department = 'CÔNG TY ĐIỆN LỰC VĨNH LONG '")
rows = cursor.fetchall()

print(f"Athletes with trailing space department in {db_file}:")
for r in rows:
    print(f"- ID: {r[0]}, Name: {r[1]}, Dept: '{r[2]}', Strava: {r[3]}, Active: {r[4]}")
    
# Also print the 16 athletes in the normal department
cursor.execute("SELECT id, full_name, department, strava_name, is_active FROM athletes WHERE department = 'CÔNG TY ĐIỆN LỰC VĨNH LONG'")
rows_16 = cursor.fetchall()
print(f"\nAthletes with normal department (16 athletes):")
for r in rows_16:
    print(f"- ID: {r[0]}, Name: {r[1]}, Dept: '{r[2]}', Strava: {r[3]}, Active: {r[4]}")

conn.close()
