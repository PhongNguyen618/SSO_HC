import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_athlete_51_in_all_backups():
    backups = [
        "SSO_HC_backup_v1.4.0_1783059852.db",
        "SSO_HC_backup_v1.4.0_1783161208.db",
        "SSO_HC_backup_v1.4.0_1783262525.db",
        "SSO_HC_backup_v1.4.0_1783313355.db"
    ]
    
    print("=== KIỂM TRA THÔNG TIN TOKEN CỦA VĐV HOÀNG THỊ HÀ (ID=51) ===")
    for b in backups:
        try:
            conn = sqlite3.connect(b)
            cur = conn.cursor()
            cur.execute("""
                SELECT id, full_name, strava_refresh_token, strava_access_token 
                FROM athletes 
                WHERE id = 51 OR full_name LIKE '%Hoàng Thị Hà%'
            """)
            rows = cur.fetchall()
            print(f"\nFile backup: {b}")
            for r in rows:
                print(f"  - ID: {r[0]} | Tên: {r[1]}")
                print(f"    Refresh Token: {r[2][:15] if r[2] else 'None'}...")
                print(f"    Access Token: {r[3][:15] if r[3] else 'None'}...")
                
                # Check xem token của Hà có trùng với ai trong bản backup này không
                if r[2]:
                    cur.execute("SELECT id, full_name FROM athletes WHERE strava_refresh_token = ? AND id != 51", (r[2],))
                    dups = cur.fetchall()
                    if dups:
                        print(f"    => TRÙNG TOKEN VỚI: {dups}")
                    else:
                        print("    => Không trùng token với ai.")
            conn.close()
        except Exception as e:
            print(f"Lỗi đọc {b}: {e}")

if __name__ == "__main__":
    check_athlete_51_in_all_backups()
