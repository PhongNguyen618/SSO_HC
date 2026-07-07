import sqlite3
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_all_dbs_historical():
    db_files = [
        "SSO_HC_backup_v1.4.0_1783262525.db",
        "SSO_HC_backup_v1.4.0_1783161208.db",
        "SSO_HC_backup_v1.4.0_1783059852.db",
        "test_sync_minh_tu.db"
    ]
    
    print("=== KIỂM TRA SỐ LƯỢNG HOẠT ĐỘNG TRƯỚC 16/06 TRONG CÁC FILE BACKUP ===")
    for db_file in db_files:
        if not os.path.exists(db_file):
            print(f"File {db_file} không tồn tại trên local.")
            continue
        try:
            conn = sqlite3.connect(db_file)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM activities WHERE activity_date < '2026-06-16'")
            count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM activities")
            total = cur.fetchone()[0]
            print(f"File: {db_file}")
            print(f"  - Số hoạt động trước 16/06: {count}")
            print(f"  - Tổng số hoạt động: {total}")
            conn.close()
        except Exception as e:
            print(f"Lỗi đọc {db_file}: {e}")

if __name__ == "__main__":
    check_all_dbs_historical()
