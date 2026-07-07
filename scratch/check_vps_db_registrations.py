import sqlite3

def check_regs():
    db_path = "SSO_HC.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT id, full_name FROM athletes WHERE full_name LIKE '%Hà%'")
    aths = cur.fetchall()
    print("Registrations for athletes matching 'Hà' in live DB:")
    for a in aths:
        cur.execute("SELECT event_id FROM competition_registrations WHERE athlete_id = ?", (a[0],))
        regs = [r[0] for r in cur.fetchall()]
        print(f"  ID: {a[0]} | Name: {a[1].encode('ascii', 'ignore').decode('ascii')} | Registered Event IDs: {regs}")
        
    conn.close()

if __name__ == "__main__":
    check_regs()
