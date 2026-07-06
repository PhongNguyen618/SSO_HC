import sqlite3
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def diagnose():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(backend_dir)
    
    print(f"Thư mục gốc quét: {root_dir}")
    print(f"Thư mục backup quét: {os.path.join(root_dir, 'static', 'uploads', 'backups')}")
    
    db_files = []
    
    # 1. Quét thư mục gốc
    if os.path.exists(root_dir):
        for f in os.listdir(root_dir):
            if f.endswith(".db"):
                db_files.append((os.path.join(root_dir, f), "Thư mục gốc"))
                
    # 2. Quét thư mục backups
    backups_dir = os.path.join(root_dir, "static", "uploads", "backups")
    if os.path.exists(backups_dir):
        for f in os.listdir(backups_dir):
            if f.endswith(".db"):
                db_files.append((os.path.join(backups_dir, f), "Thư mục static backups"))
                
    # 3. Quét thư mục old_and_backup nếu có
    old_backup_dir = os.path.join(root_dir, "old_and_backup")
    if os.path.exists(old_backup_dir):
        for f in os.listdir(old_backup_dir):
            if f.endswith(".db"):
                db_files.append((os.path.join(old_backup_dir, f), "Thư mục old_and_backup"))

    print(f"\nTìm thấy tổng cộng {len(db_files)} file .db:")
    for path, location in db_files:
        filename = os.path.basename(path)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        try:
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            
            # Kiểm tra xem bảng activities có tồn tại không
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activities'")
            table_exists = cur.fetchone()
            
            if table_exists:
                cur.execute("SELECT COUNT(*) FROM activities")
                count = cur.fetchone()[0]
                print(f"  - {filename} | Vị trí: {location} | Dung lượng: {size_mb:.2f} MB | Số hoạt động: {count} ✅")
            else:
                print(f"  - {filename} | Vị trí: {location} | Dung lượng: {size_mb:.2f} MB | Không có bảng activities ❌")
            conn.close()
        except Exception as e:
            print(f"  - {filename} | Vị trí: {location} | Dung lượng: {size_mb:.2f} MB | Lỗi kết nối: {e} ❌")

if __name__ == "__main__":
    diagnose()
