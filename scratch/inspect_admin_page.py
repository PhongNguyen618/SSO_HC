import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Cài đặt biến môi trường giả lập
os.environ["APP_URL"] = "http://localhost:8001"
os.environ["DATABASE_URL"] = "sqlite:///SSO_HC_backup_v1.4.0_1783313355.db"

# Thêm đường dẫn thư mục hiện tại để Python tìm thấy backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database import SessionLocal, Athlete
from fastapi.testclient import TestClient

def save_admin_page_to_inspect():
    client = TestClient(app)
    db = SessionLocal()
    try:
        import backend.auth as auth
        
        # Tìm một admin athlete (có id nằm trong bảng VĐV)
        admin_athlete = db.query(Athlete).filter(Athlete.is_active == 1).first()
        print(f"Mocking admin session for athlete: {admin_athlete.full_name}")
        
        # Mock hàm kiểm tra session
        auth.get_admin_session = lambda req, database: admin_athlete
        
        response = client.get("/admin")
        print(f"Response status: {response.status_code}")
        
        # Ghi nội dung HTML ra file để kiểm tra
        output_file = "scratch/rendered_admin_inspect.html"
        with io.open(output_file, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"Đã lưu nội dung trang Admin vào: {output_file}")
        
        # Tìm xem chuỗi "CẢNH BÁO" có xuất hiện không
        if "CẢNH BÁO" in response.text:
            print("Tìm thấy từ khóa 'CẢNH BÁO' trong HTML!")
        else:
            print("Không tìm thấy từ khóa 'CẢNH BÁO'!")
            
    finally:
        db.close()

if __name__ == "__main__":
    save_admin_page_to_inspect()
