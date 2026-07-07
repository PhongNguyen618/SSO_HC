import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_ha_hoang():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    conn = sqlite3.connect(db_backup)
    cur = conn.cursor()
    
    # 1. Search athletes table
    print("=== Searching athletes table in Backup DB ===")
    cur.execute("SELECT id, full_name, strava_name, department, is_active, strava_refresh_token FROM athletes WHERE full_name LIKE '%Hà%' OR full_name LIKE '%Ha%'")
    rows = cur.fetchall()
    for r in rows:
        print(f"ID: {r[0]} | Name: {r[1]} | Strava Name: {r[2]} | Dept: {r[3]} | Active: {r[4]} | Has Token: {r[5] is not None}")
        
    print("\n=== Searching activities for any athlete named Ha / Hoàng ===")
    # Let's find activities belonging to these athlete IDs or with athlete_name_raw containing "Ha" or "Hà"
    for r in rows:
        ath_id = r[0]
        cur.execute("SELECT COUNT(*), MIN(activity_date), MAX(activity_date) FROM activities WHERE athlete_id = ?", (ath_id,))
        count, min_date, max_date = cur.fetchone()
        print(f"Athlete ID {ath_id} ({r[1]}): {count} activities (from {min_date} to {max_date})")
        
        # Check registrations
        cur.execute("SELECT event_id FROM competition_registrations WHERE athlete_id = ?", (ath_id,))
        regs = cur.fetchall()
        print(f"  Registered events: {[reg[0] for reg in regs]}")
        
    conn.close()

if __name__ == "__main__":
    check_ha_hoang()
