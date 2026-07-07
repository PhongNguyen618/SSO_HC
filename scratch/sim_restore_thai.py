import sqlite3
import unicodedata
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def simulate_restore_for_thai():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    db_live = "SSO_HC_backup_v1.4.0_1783345876.db"
    
    conn_b = sqlite3.connect(db_backup)
    cur_b = conn_b.cursor()
    
    conn_l = sqlite3.connect(db_live)
    cur_l = conn_l.cursor()
    
    # Lấy activities của Thái từ backup
    cur_b.execute("SELECT * FROM activities WHERE athlete_id = 44")
    col_names = [desc[0] for desc in cur_b.description]
    acts = [dict(zip(col_names, r)) for r in cur_b.fetchall()]
    
    print(f"Tổng số hoạt động của Thái trong backup: {len(acts)}")
    
    skipped_exist = 0
    skipped_date = 0
    skipped_event = 0
    to_restore = 0
    
    for act in acts:
        # Check date
        if act.get("activity_date") and act["activity_date"] >= "2026-06-16":
            skipped_date += 1
            continue
            
        # Check event_id
        if act.get("event_id") != 1:
            skipped_event += 1
            continue
            
        # Check existing in live
        cur_l.execute("SELECT id FROM activities WHERE id = ?", (act["id"],))
        existing = cur_l.fetchone()
        if existing:
            skipped_exist += 1
            continue
            
        to_restore += 1
        if to_restore <= 5:
            print(f"Hoạt động hợp lệ để restore: ID={act['id']} | Ngày={act['activity_date']} | Cự ly={act['distance_km']}")

    print("\n--- KẾT QUẢ CHẨN ĐOÁN GIẢ LẬP KHÔI PHỤC ---")
    print(f"Bỏ qua do ngày >= 16/06: {skipped_date}")
    print(f"Bỏ qua do event_id != 1: {skipped_event}")
    print(f"Bỏ qua do ĐÃ TỒN TẠI TRONG CSDL LIVE: {skipped_exist}")
    print(f"Số lượng hoạt động SẼ ĐƯỢC CHÈN VÀO: {to_restore}")
    
    conn_b.close()
    conn_l.close()

if __name__ == "__main__":
    simulate_restore_for_thai()
