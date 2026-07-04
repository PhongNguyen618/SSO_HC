# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

def restore_activities():
    # 1. Tìm file backup tự động mới nhất
    backups_dir = os.path.join("static", "uploads", "backups")
    backup_db = None
    
    if os.path.exists(backups_dir):
        files = sorted([f for f in os.listdir(backups_dir) if f.endswith(".db")])
        if files:
            backup_db = os.path.join(backups_dir, files[-1])
            
    if not backup_db or not os.path.exists(backup_db):
        print("[Loi] Khong tim thay file CSDL backup tu dong trong thu muc: static/uploads/backups/")
        return

    print(f"[*] Dang doc du lieu tu file backup: {backup_db}")
    
    # 2. Doc cac hoat dong cua Hoàng Thị Hà (ID 51) tu backup
    conn_b = sqlite3.connect(backup_db)
    cur_b = conn_b.cursor()
    try:
        cur_b.execute("SELECT * FROM activities WHERE athlete_id = 51 AND activity_date < '2026-06-16'")
        col_names = [description[0] for description in cur_b.description]
        rows = cur_b.fetchall()
    except Exception as e:
        print(f"[Loi] Khong the doc bang activities tu backup: {e}")
        return
    finally:
        conn_b.close()
        
    print(f"[*] Tim thay {len(rows)} hoat dong cua Hoàng Thị Hà (ID 51) tu file backup.")
    if not rows:
        print("[!] Khong co du lieu hoat dong nao cua ID 51 trong backup de khoi phuc.")
        return

    # 3. Khoi phuc vao CSDL hien tai (SSO_HC.db)
    live_db = "SSO_HC.db"
    if not os.path.exists(live_db):
        print(f"[!] Khong tim thay file CSDL hien tai '{live_db}' trong thu muc goc.")
        live_db = input("Vui long nhap duong dan toi file CSDL live (vi du: SSO_HC.db): ").strip()
        if not os.path.exists(live_db):
            print("[Loi] File khong ton tai. Thoat.")
            return

    print(f"[*] Dang tien hanh khoi phuc vao: {live_db}...")
    conn_t = sqlite3.connect(live_db)
    cur_t = conn_t.cursor()
    
    inserted = 0
    skipped = 0
    
    for r in rows:
        act_id = r[0]
        cur_t.execute("SELECT id FROM activities WHERE id = ?", (act_id,))
        if cur_t.fetchone():
            skipped += 1
            continue
            
        placeholders = ", ".join(["?"] * len(col_names))
        columns = ", ".join(col_names)
        query = f"INSERT INTO activities ({columns}) VALUES ({placeholders})"
        
        cur_t.execute(query, r)
        inserted += 1
        
    conn_t.commit()
    conn_t.close()
    
    print("====================================================")
    print(f"[OK] Khoi phuc hoan tat!")
    print(f"  - So hoat dong da khoi phuc thanh cong: {inserted}")
    print(f"  - So hoat dong bi trung lap (da ton tai): {skipped}")
    print("====================================================")

if __name__ == "__main__":
    restore_activities()
