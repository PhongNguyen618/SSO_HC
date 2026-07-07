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

def analyze_restoration_gaps_correctly():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    db_live = "SSO_HC_backup_v1.4.0_1783345876.db"
    
    conn_b = sqlite3.connect(db_backup)
    cur_b = conn_b.cursor()
    
    conn_l = sqlite3.connect(db_live)
    cur_l = conn_l.cursor()
    
    # 1. Lấy tất cả VĐV từ backup
    cur_b.execute("SELECT id, full_name FROM athletes")
    backup_athletes = cur_b.fetchall()
    
    # 2. Lấy tất cả VĐV từ live
    cur_l.execute("SELECT id, full_name FROM athletes")
    live_athletes_map = {normalize_name(r[1]): r[0] for r in cur_l.fetchall()}
    
    gaps = []
    
    for b_id, b_name in backup_athletes:
        norm_name = normalize_name(b_name)
        
        # Đếm số hoạt động lịch sử (< 16/06) của VĐV này trong backup
        cur_b.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ? AND activity_date < '2026-06-16' AND event_id = 1", (b_id,))
        b_count = cur_b.fetchone()[0]
        
        if b_count == 0:
            continue
            
        # Tìm VĐV tương ứng trong live
        if norm_name not in live_athletes_map:
            gaps.append({
                "name": b_name,
                "backup_id": b_id,
                "backup_count": b_count,
                "live_count": 0,
                "reason": "Không tìm thấy tên VĐV này trong bảng athletes của CSDL live hiện tại"
            })
            continue
            
        l_id = live_athletes_map[norm_name]
        # Đếm số hoạt động lịch sử trong live
        cur_l.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ? AND activity_date < '2026-06-16' AND event_id = 1", (l_id,))
        l_count = cur_l.fetchone()[0]
        
        if l_count < b_count:
            gaps.append({
                "name": b_name,
                "backup_id": b_id,
                "backup_count": b_count,
                "live_count": l_count,
                "reason": f"Bị thiếu {b_count - l_count} hoạt động lịch sử trước 16/06"
            })
            
    print(f"=== ĐỐI CHIẾU THỰC TẾ: TỔNG CỘNG {len(gaps)} VĐV BỊ THIẾU HOẠT ĐỘNG LỊCH SỬ ===")
    for g in gaps:
        print(f"VĐV: '{g['name']}' (ID backup: {g['backup_id']})")
        print(f"  Số hoạt động trong Backup: {g['backup_count']}")
        print(f"  Số hoạt động trong Live  : {g['live_count']}")
        print(f"  Trạng thái               : {g['reason']}")
        print("-" * 50)
        
    conn_b.close()
    conn_l.close()

if __name__ == "__main__":
    analyze_restoration_gaps_correctly()
