import sqlite3
import sys
import io

# Đảm bảo in ra UTF-8 không lỗi trên terminal
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_mai_hoa():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    db_active = "SSO_HC.db"
    
    for db_name, db_path in [("BACKUP DB", db_backup), ("ACTIVE DB", db_active)]:
        print(f"\n==================== {db_name} ({db_path}) ====================")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 1. Tìm thông tin VĐV trong bảng athletes
            print("--- Athletes Info ---")
            cursor.execute("SELECT id, full_name, department, gender, weight, strava_name, strava_athlete_id, strava_refresh_token FROM athletes WHERE full_name LIKE '%Hoa%' OR strava_name LIKE '%Hoa%'")
            athletes = cursor.fetchall()
            if not athletes:
                print("No athletes matching 'Hoa' found.")
            for ath in athletes:
                print(f"ID: {ath[0]}, Name: {ath[1]}, Dept: {ath[2]}, Gender: {ath[3]}, Weight: {ath[4]}, Strava Name: {ath[5]}, Strava ID: {ath[6]}, Has Token: {bool(ath[7])}")
                
                # 2. Tìm các đăng ký giải đấu
                cursor.execute("SELECT event_id FROM competition_registrations WHERE athlete_id = ?", (ath[0],))
                regs = cursor.fetchall()
                print(f"  Registered Events IDs: {[r[0] for r in regs]}")
                
                # 3. Đếm số lượng hoạt động trong DB của VĐV này
                cursor.execute("SELECT COUNT(*), SUM(distance_km), SUM(kcal_burned) FROM activities WHERE athlete_id = ?", (ath[0],))
                act_summary = cursor.fetchone()
                print(f"  Activities count: {act_summary[0]}, Total Distance: {act_summary[1]} km, Total Kcal: {act_summary[2]} kcal")
                
                # 4. Liệt kê một số hoạt động của VĐV này
                cursor.execute("SELECT id, name, type, sport_type, distance_km, kcal_burned, activity_date, multiplier FROM activities WHERE athlete_id = ? ORDER BY activity_date DESC LIMIT 5", (ath[0],))
                acts = cursor.fetchall()
                if acts:
                    print("  Recent 5 activities:")
                    for act in acts:
                        print(f"    ID: {act[0]} | Name: {act[1]} | Type: {act[2]}/{act[3]} | Dist: {act[4]} | Kcal: {act[5]} | Date: {act[6]} | Mult: {act[7]}")
                else:
                    print("  No activities found.")
            
            conn.close()
        except Exception as e:
            print(f"Error checking {db_path}: {e}")

if __name__ == "__main__":
    check_mai_hoa()
