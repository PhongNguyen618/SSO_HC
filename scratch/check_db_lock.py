import sqlite3
import time

print("Connecting to DB...")
start = time.time()
try:
    conn = sqlite3.connect("SSO_HC.db", timeout=5)
    cursor = conn.cursor()
    print("Connected in", time.time() - start)
    
    print("Running count query on activities...")
    start = time.time()
    cursor.execute("SELECT COUNT(*) FROM activities")
    row = cursor.fetchone()
    print("Count:", row[0], "in", time.time() - start)
    
    print("Running select query...")
    start = time.time()
    cursor.execute("SELECT * FROM activities LIMIT 5")
    rows = cursor.fetchall()
    print(f"Fetched {len(rows)} rows in", time.time() - start)
    
    conn.close()
    print("Success")
except Exception as e:
    print("Error:", e)
