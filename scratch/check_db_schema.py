import sqlite3

def check_tables():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    conn = sqlite3.connect(db_backup)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("Tables:", cur.fetchall())
    conn.close()

if __name__ == "__main__":
    check_tables()
