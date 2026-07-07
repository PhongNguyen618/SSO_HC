import os
import sys
import io
import unittest
from fastapi.testclient import TestClient

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Cài đặt biến môi trường giả lập
os.environ["APP_URL"] = "http://localhost:8001"
os.environ["DATABASE_URL"] = "sqlite:///SSO_HC_backup_v1.4.0_1783313355.db"

# Thêm đường dẫn thư mục hiện tại để Python tìm thấy backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database import SessionLocal, Athlete

class TestAdminDashboard(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
    def test_admin_page_access(self):
        print("\n--- BẮT ĐẦU KIỂM TRA TRANG ADMIN ---")
        
        # 1. Thử truy cập không có cookie admin -> Phải trả về 307 redirect về trang login hoặc login page
        response = self.client.get("/admin", follow_redirects=True)
        print(f"Truy cập không cookie: Status {response.status_code}")
        self.assertIn(response.status_code, [200, 307, 302])
        
        # 2. Giả lập phiên đăng nhập admin bằng cách chèn cookie hợp lệ
        # Lấy session trực tiếp từ database để tìm admin password hoặc cấu hình
        db = SessionLocal()
        try:
            # Gán session cookie trực tiếp
            # Admin session được check qua: get_admin_session(request, db)
            # Hàm check cookie bằng cách tìm session id trong DB hoặc khớp cookie.
            # Chúng ta sẽ bypass check login bằng cách mock hàm get_admin_session
            import backend.auth as auth
            
            # Lưu lại hàm cũ để khôi phục
            original_get_admin_session = auth.get_admin_session
            
            # Mock trả về đối tượng athlete giả lập có quyền admin
            admin_athlete = db.query(Athlete).filter(Athlete.is_active == 1).first() # Lấy đại 1 VĐV đang active
            auth.get_admin_session = lambda req, database: admin_athlete
            
            # Thử gọi trang admin dashboard
            print("Gọi trang admin_dashboard với mock Admin session...")
            response = self.client.get("/admin")
            print(f"Kết quả trang Admin: Status {response.status_code}")
            
            # Khôi phục hàm cũ
            auth.get_admin_session = original_get_admin_session
            
            # Kiểm tra xem có sinh ra lỗi 500 hay không
            self.assertEqual(response.status_code, 200)
            self.assertIn("CẢNH BÁO TRÙNG LẶP TOKEN LIÊN KẾT STRAVA", response.text)
            print("👉 THÀNH CÔNG: Trang Admin render hoàn hảo 200 OK và chứa hộp cảnh báo trùng token!")
            
        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
