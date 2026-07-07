import sqlite3

def check_integrity():
    try:
        conn = sqlite3.connect("SSO_HC.db")
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        print("Integrity check result:", result)
        conn.close()
    except Exception as e:
        print("Error checking integrity:", e)

if __name__ == "__main__":
    check_integrity()
