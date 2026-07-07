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

def analyze_restoration_gaps():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    db_live = "SSO_HC_backup_v1.4.0_1783345876.db"
    
    conn_b = sqlite3.connect(db_backup)
    cur_b = conn_b.cursor()
    
    conn_l = sqlite3.connect(db_live)
    cur_l = conn_l.cursor()
    
    # 1. Lấy danh sách VĐV trong backup gốc và số lượng hoạt động lịch sử (< 16/06) của họ ở giải 1
    cur_b.execute("""
        SELECT a.id, a.full_name, COUNT(act.id)
        FROM athletes a
        LEFT JOIN activities act ON a.id = act.athlete_id
        WHERE act.activity_date < '2026-06-16' AND act.event_id = 1
        GROUP BY a.id
    """)
    backup_athletes = {normalize_name(r[1]): {"name": r[1], "id": r[0], "backup_count": r[2]} for r in cur_b.fetchall()}
    
    # 2. Lấy danh sách VĐV trong DB live hiện tại và số lượng hoạt động lịch sử (< 16/06) của họ ở giải 1
    cur_l.execute("""
        SELECT a.id, a.full_name, COUNT(act.id)
        FROM athletes a
        LEFT JOIN activities act ON a.id = act.athlete_id
        WHERE act.activity_date < '2026-06-16' AND act.event_id = 1
        GROUP BY a.id
    """)
    live_athletes = {normalize_name(r[1]): {"name": r[1], "id": r[0], "live_count": r[2]} for r in cur_l.fetchall()}
    
    # 3. Đối chiếu so khớp tìm khoảng trống (gap)
    gaps = []
    for norm_name, b_info in backup_athletes.items():
        backup_count = b_info["backup_count"]
        
        # Nếu VĐV không tồn tại trong live
        if norm_name not in live_athletes:
            gaps.append({
                "name": b_info["name"],
                "backup_id": b_info["id"],
                "backup_count": backup_count,
                "live_count": 0,
                "reason": "Không tìm thấy VĐV trên CSDL live hiện tại (lệch tên hoặc chưa đăng ký)"
            })
            continue
            
        live_count = live_athletes[norm_name]["live_count"]
        # Nếu số lượng hoạt động trong live bị thiếu
        if live_count < backup_count:
            gaps.append({
                "name": b_info["name"],
                "backup_id": b_info["id"],
                "backup_count": backup_count,
                "live_count": live_count,
                "reason": f"Bị thiếu {backup_count - live_count} hoạt động lịch sử"
            })
            
    print(f"=== PHÂN TÍCH KHOẢNG TRỐNG DỮ LIỆU KHÔI PHỤC (Tổng cộng {len(gaps)} VĐV bị thiếu) ===")
    for g in gaps:
        print(f"VĐV: '{g['name']}' (ID gốc: {g['backup_id']})")
        print(f"  Số hoạt động trong Backup: {g['backup_count']}")
        print(f"  Số hoạt động trong Live  : {g['live_count']}")
        print(f"  Lý do/Trạng thái         : {g['reason']}")
        print("-" * 50)
        
    conn_b.close()
    conn_l.close()

if __name__ == "__main__":
    analyze_restoration_gaps()
