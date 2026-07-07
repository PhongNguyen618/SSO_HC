import sqlite3
import sys

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

def check_configs():
    conn = sqlite3.connect("SSO_HC.db")
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM configs")
    rows = cursor.fetchall()
    print("Cac cau hinh trong bang configs:")
    for row in rows:
        print(f"Key: {row[0]} | Value: {row[1]}")
    conn.close()

if __name__ == "__main__":
    check_configs()
