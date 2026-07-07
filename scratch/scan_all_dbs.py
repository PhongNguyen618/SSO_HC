import os
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def find_all_db_files():
    print("=== DANH SÁCH FILE DATABASE TRÊN HỆ THỐNG ===")
    
    # Quét thư mục gốc và thư mục backups
    db_candidates = []
    
    # 1. Quét thư mục gốc
    for file in os.listdir("."):
        if file.endswith(".db"):
            db_candidates.append(file)
            
    # 2. Quét thư mục backups
    backups_dir = "backups"
    if os.path.exists(backups_dir):
        for file in os.listdir(backups_dir):
            if file.endswith(".db"):
                db_candidates.append(os.path.join(backups_dir, file))
                
    for db_path in db_candidates:
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            
            # Đếm số hoạt động lịch sử trước 16/06
            cur.execute("SELECT COUNT(*) FROM activities WHERE activity_date < '2026-06-16' AND event_id = 1")
            hist_count = cur.fetchone()[0]
            
            # Đếm số hoạt động của Lê Văn Thái (ID=44 hoặc tìm theo tên)
            cur.execute("SELECT id FROM athletes WHERE full_name LIKE '%Lê Văn Thái%'")
            ath = cur.fetchone()
            thai_count = 0
            if ath:
                cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ? AND activity_date < '2026-06-16' AND event_id = 1", (ath[0],))
                thai_count = cur.fetchone()[0]
                
            file_size = os.path.getsize(db_path) / (1024 * 1024) # MB
            
            print(f"File: '{db_path}' ({file_size:.2f} MB)")
            print(f"  - Số hoạt động lịch sử (< 16/06): {hist_count}")
            print(f"  - Số hoạt động của Lê Văn Thái   : {thai_count}")
            conn.close()
        except Exception as e:
            print(f"File: '{db_path}' -> Bị lỗi đọc: {e}")
            
if __name__ == "__main__":
    find_all_db_files()
