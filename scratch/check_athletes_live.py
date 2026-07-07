import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_athletes_in_live():
    db_live = "SSO_HC_backup_v1.4.0_1783345876.db"
    conn = sqlite3.connect(db_live)
    cur = conn.cursor()
    
    # Danh sách VĐV bị báo không tìm thấy
    missing_names = [
        "Nguyễn Mạnh Tùng",
        "Lê Đặng Xuân Tân",
        "Lê Hiếu Minh",
        "TÔN THẤT PHÚC THỊNH",
        "Huỳnh Thị Minh Châu",
        "Bùi Văn Trình",
        "Nguyễn Cảnh Chương",
        "Nguyễn Trọng Tuấn",
        "Hoàng Anh Đức",
        "Lê Văn Thái",
        "Trần Ngọc Anh Tuấn"
    ]
    
    print("=== TÌM KIẾM VĐV BỊ THIẾU TRONG BẢNG ATHLETES CỦA CSDL LIVE ===")
    for name in missing_names:
        cur.execute("SELECT id, full_name, department, is_active FROM athletes WHERE full_name LIKE ?", (f"%{name}%",))
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"Khớp tên: '{name}' -> Tìm thấy trong live: ID={r[0]} | Tên đầy đủ: '{r[1]}' | Phòng: '{r[2]}' | Active: {r[3]}")
        else:
            print(f"❌ KHÔNG TÌM THẤY BẤT KỲ VĐV NÀO khớp với tên '{name}' trong bảng athletes của CSDL live!")
            
    conn.close()

if __name__ == "__main__":
    check_athletes_in_live()
