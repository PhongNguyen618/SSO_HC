import sqlite3
import unicodedata
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def normalize_name(name):
    if not name:
        return ""
    name_nfc = unicodedata.normalize("NFC", name)
    return name_nfc.replace("*", "").strip().lower()

def debug_restore_on_these_dbs():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    db_live = "SSO_HC_backup_v1.4.0_1783345876.db"
    
    # 1. Đọc dữ liệu từ file backup
    conn_b = sqlite3.connect(db_backup)
    cur_b = conn_b.cursor()
    cur_b.execute("SELECT id, full_name, strava_name FROM athletes")
    backup_athletes = cur_b.fetchall()
    
    backup_data = {}
    for a_id, name, s_name in backup_athletes:
        cur_b.execute("SELECT * FROM activities WHERE athlete_id = ?", (a_id,))
        col_names = [desc[0] for desc in cur_b.description]
        rows = cur_b.fetchall()
        backup_data[a_id] = {
            "name": name,
            "strava_name": s_name,
            "activities": [dict(zip(col_names, r)) for r in rows]
        }
    conn_b.close()
    
    # 2. Đọc dữ liệu từ file live
    conn_l = sqlite3.connect(db_live)
    cur_l = conn_l.cursor()
    cur_l.execute("SELECT id, full_name FROM athletes")
    live_athletes = cur_l.fetchall()
    live_name_map = {normalize_name(r[1]): r[0] for r in live_athletes}
    
    print("=== CHẠY GIẢ LẬP KHÔI PHỤC CHI TIẾT CHO LÊ VĂN THÁI ===")
    
    target_ath_id = 44 # Lê Văn Thái
    info = backup_data[target_ath_id]
    name = info["name"]
    acts = info["activities"]
    
    print(f"Họ Tên trong backup: '{name}'")
    print(f"Số lượng hoạt động trong backup: {len(acts)}")
    
    norm_name = normalize_name(name)
    if norm_name not in live_name_map:
        print(f"❌ LỖI: Tên chuẩn hóa '{norm_name}' không tồn tại trong live_name_map!")
    else:
        new_id = live_name_map[norm_name]
        print(f"✅ Khớp thành công VĐV! ID mới trong live: {new_id}")
        
        valid_count = 0
        inserted_count = 0
        skipped_exist = 0
        skipped_date = 0
        skipped_event = 0
        
        for act in acts:
            # Check date
            if act.get("activity_date") and act["activity_date"] >= "2026-06-16":
                skipped_date += 1
                continue
                
            # Check event_id
            if act.get("event_id") != 1:
                skipped_event += 1
                continue
                
            valid_count += 1
            
            # Check existing
            cur_l.execute("SELECT id FROM activities WHERE id = ?", (act["id"],))
            existing = cur_l.fetchone()
            if existing:
                skipped_exist += 1
                continue
                
            inserted_count += 1
            
        print(f"Kết quả xử lý 195 hoạt động:")
        print(f"  - Bỏ qua do ngày >= 16/06: {skipped_date}")
        print(f"  - Bỏ qua do event_id != 1: {skipped_event}")
        print(f"  - Bỏ qua do ĐÃ TỒN TẠI trong live: {skipped_exist}")
        print(f"  - Sẽ được thêm mới (Insert): {inserted_count}")
        
    conn_l.close()

if __name__ == "__main__":
    debug_restore_on_these_dbs()
