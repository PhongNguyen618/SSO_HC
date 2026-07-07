import os
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def find_largest_backup():
    root_dir = "c:\\Users\\PC\\Desktop\\SSO_HC"
    
    # Danh sách các file DB cần quét
    db_files = []
    
    # Quét thư mục gốc
    for f in os.listdir(root_dir):
        if f.endswith(".db"):
            db_files.append(os.path.join(root_dir, f))
            
    # Quét thư mục backup tự động
    backups_dir = os.path.join(root_dir, "static", "uploads", "backups")
    if os.path.exists(backups_dir):
        for f in os.listdir(backups_dir):
            if f.endswith(".db"):
                db_files.append(os.path.join(backups_dir, f))
                
    results = []
    for db_path in db_files:
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            
            # Đếm tổng số hoạt động
            cur.execute("SELECT COUNT(*) FROM activities")
            total = cur.fetchone()[0]
            
            # Đếm hoạt động trước ngày 16/06/2026 (Lịch sử)
            cur.execute("SELECT COUNT(*) FROM activities WHERE activity_date < '2026-06-16'")
            before_16 = cur.fetchone()[0]
            
            # Đếm hoạt động từ ngày 16/06/2026 trở đi (Mới)
            cur.execute("SELECT COUNT(*) FROM activities WHERE activity_date >= '2026-06-16'")
            after_16 = cur.fetchone()[0]
            
            # Đếm tổng số vận động viên
            cur.execute("SELECT COUNT(*) FROM athletes")
            athletes = cur.fetchone()[0]
            
            conn.close()
            
            results.append({
                "path": db_path,
                "filename": os.path.basename(db_path),
                "total": total,
                "before_16": before_16,
                "after_16": after_16,
                "athletes": athletes,
                "size_mb": os.path.getsize(db_path) / (1024 * 1024)
            })
        except Exception:
            continue
            
    # Sắp xếp theo số lượng hoạt động lịch sử trước 16/06 giảm dần
    results = sorted(results, key=lambda x: x["before_16"], reverse=True)
    
    print("=== THỐNG KÊ CHI TIẾT CÁC FILE CSDL BACKUP HIỆN CÓ ===")
    for idx, r in enumerate(results, 1):
        print(f"{idx}. File: '{r['filename']}'")
        print(f"   Dung lượng: {r['size_mb']:.2f} MB")
        print(f"   Tổng số VĐV: {r['athletes']} người")
        print(f"   Tổng số hoạt động: {r['total']}")
        print(f"   👉 Hoạt động LỊCH SỬ (trước 16/06): {r['before_16']}")
        print(f"   👉 Hoạt động MỚI (từ 16/06): {r['after_16']}")
        print("-" * 60)

if __name__ == "__main__":
    find_largest_backup()
