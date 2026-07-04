# -*- coding: utf-8 -*-
import sqlite3
import os

def normalize_name(name):
    if not name:
        return ""
    # Strip asterisks, extra spaces, and convert to lower
    return name.replace("*", "").strip().lower()

def restore_all():
    # 1. Find the latest auto backup database
    backups_dir = os.path.join("static", "uploads", "backups")
    backup_db = None
    
    if os.path.exists(backups_dir):
        files = sorted([f for f in os.listdir(backups_dir) if f.endswith(".db")])
        if files:
            backup_db = os.path.join(backups_dir, files[-1])
            
    if not backup_db or not os.path.exists(backup_db):
        print("[Loi] Khong tim thay file CSDL backup tu dong trong: static/uploads/backups/")
        return

    print(f"[*] File backup su dung: {backup_db}")
    
    # 2. Read athletes and activities from backup
    conn_b = sqlite3.connect(backup_db)
    cur_b = conn_b.cursor()
    try:
        cur_b.execute("SELECT id, full_name, strava_name FROM athletes")
        backup_athletes = cur_b.fetchall()
        
        backup_data = {}
        for a_id, name, s_name in backup_athletes:
            cur_b.execute("SELECT * FROM activities WHERE athlete_id = ? AND activity_date < '2026-06-16'", (a_id,))
            col_names = [desc[0] for desc in cur_b.description]
            rows = cur_b.fetchall()
            backup_data[a_id] = {
                "name": name,
                "strava_name": s_name,
                "activities": [dict(zip(col_names, r)) for r in rows]
            }
    except Exception as e:
        print(f"[Loi] Khong the doc tu CSDL backup: {e}")
        return
    finally:
        conn_b.close()
        
    # 3. Connect to live database (SSO_HC.db)
    live_db = "SSO_HC.db"
    if not os.path.exists(live_db):
        print(f"[!] Khong tim thay CSDL hien tai '{live_db}' trong thu muc goc.")
        live_db = input("Vui long nhap duong dan den file CSDL live (vi du: SSO_HC.db): ").strip()
        if not os.path.exists(live_db):
            print("[Loi] File khong ton tai. Thoat.")
            return
            
    print(f"[*] Dang ket noi va khoi phuc vao: {live_db}...")
    conn_l = sqlite3.connect(live_db)
    cur_l = conn_l.cursor()
    
    # Get live athletes for name matching
    cur_l.execute("SELECT id, full_name FROM athletes")
    live_athletes = cur_l.fetchall()
    live_name_map = {normalize_name(ath[1]): ath[0] for ath in live_athletes}
    
    total_restored = 0
    
    for old_id, info in backup_data.items():
        name = info["name"]
        acts = info["activities"]
        if not acts:
            continue
            
        norm_name = normalize_name(name)
        if norm_name not in live_name_map:
            print(f"[Canh bao] Khong tim thay VDV '{name}' trong CSDL live.")
            continue
            
        new_id = live_name_map[norm_name]
        
        inserted = 0
        skipped = 0
        
        for act in acts:
            # Update athlete_id to match the live DB ID
            act["athlete_id"] = new_id
            
            # Check if this activity already exists in live
            cur_l.execute("SELECT id FROM activities WHERE id = ?", (act["id"],))
            if cur_l.fetchone():
                skipped += 1
                continue
                
            col_names = list(act.keys())
            placeholders = ", ".join(["?"] * len(col_names))
            columns = ", ".join(col_names)
            query = f"INSERT INTO activities ({columns}) VALUES ({placeholders})"
            
            cur_l.execute(query, tuple(act.values()))
            inserted += 1
            total_restored += 1
            
        if inserted > 0:
            print(f"  + Da khoi phuc {inserted} hoat dong cho VDV: {name} (ID moi: {new_id})")
            
    conn_l.commit()
    conn_l.close()
    
    print("====================================================")
    print(f"[OK] Khoi phuc hoan tat!")
    print(f"  - Tong so hoat dong duoc khoi phuc: {total_restored}")
    print("====================================================")

if __name__ == "__main__":
    restore_all()
