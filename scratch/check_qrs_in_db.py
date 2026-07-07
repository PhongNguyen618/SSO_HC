import sqlite3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_qrs():
    conn = sqlite3.connect("SSO_HC_backup_v1.4.0_1783059852.db")
    cursor = conn.cursor()
    
    # 1. Check configs table
    print("=== CONFIGS TABLE ===")
    cursor.execute("SELECT key, value FROM configs WHERE key LIKE '%qr%' OR key LIKE '%zalo%'")
    rows = cursor.fetchall()
    for row in rows:
        print(f"Key: {row[0]} -> Value: {row[1]}")
        
    # 2. Check competition_events rules_group_qr
    print("\n=== EVENT RULES GROUP QR ===")
    cursor.execute("SELECT id, title, rules_group_qr, is_active FROM competition_events")
    events = cursor.fetchall()
    for ev in events:
        print(f"ID: {ev[0]}, Title: {ev[1]}, Rules QR: {ev[2]}, Active: {ev[3]}")
        
    conn.close()

if __name__ == "__main__":
    check_qrs()
