import sqlite3

def check_dates():
    db_backup = "SSO_HC_backup_v1.4.0_1783161208.db"
    conn = sqlite3.connect(db_backup)
    cur = conn.cursor()
    cur.execute("SELECT id, title, start_date, end_date, is_active FROM competition_events")
    for r in cur.fetchall():
        print(f"ID: {r[0]} | Title: {r[1]} | Start: {r[2]} | End: {r[3]} | Active: {r[4]}")
    conn.close()

if __name__ == "__main__":
    check_dates()
