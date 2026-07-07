import os
import sys
import io
import unittest
from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from starlette.datastructures import Headers

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Tạo đối tượng request giả lập có url
scope = {
    "type": "http",
    "method": "GET",
    "path": "/register",
    "headers": Headers(raw=[(b"host", b"localhost:8000")]).raw,
}
dummy_request = Request(scope)

def test_template_compilation():
    templates_dir = "c:\\Users\\PC\\Desktop\\SSO_HC\\templates"
    env = Environment(loader=FileSystemLoader(templates_dir))
    
    # Giả lập bộ lọc currency (nếu template có dùng)
    def dummy_currency(value):
        return f"{value} VND"
    env.filters['currency'] = dummy_currency
    
    # Giả lập hàm get_configs toàn cục
    env.globals['get_configs'] = lambda *args, **kwargs: {}
    env.globals['get_admin_session'] = lambda *args, **kwargs: None
    env.globals['url_for'] = lambda name, **kwargs: f"/static/{kwargs.get('filename', '')}"
    
    print("=== BẮT ĐẦU KIỂM TRA BIÊN DỊCH TEMPLATE ===")
    
    # 1. Kiểm tra register.html
    try:
        template_register = env.get_template("register.html")
        # Giả lập context truyền vào
        context_register = {
            "request": dummy_request,
            "configs": {"rules_group_qr": "http://example.com/qr.png", "strava_club_id": "12345"},
            "app_configs": {"rules_group_qr": "http://example.com/qr.png", "strava_club_id": "12345"},
            "departments": ["SSO - KẾ HOẠCH", "SSO - ĐIỀU ĐỘ"],
            "active_competitions": [],
            "selected_event_id": 1,
            "unlinked_athletes": ["Nguyễn Văn A"],
            "success": "Đăng ký thành công!",
            "error": None,
            "already_exists": False,
            "needs_strava_auth": True,
            "auth_url": "http://strava.com/oauth",
            "athlete_id": 1,
            "athlete_name": "Nguyễn Văn A",
            "form_data": {}
        }
        rendered_reg = template_register.render(context_register)
        print("✅ Biên dịch 'register.html': THÀNH CÔNG!")
        
        # Kiểm tra xem mã JS confirmOAuthLink có được render ra không
        if "function confirmOAuthLink" in rendered_reg:
            print("   -> JS confirmOAuthLink tồn tại trong HTML kết quả!")
        else:
            print("   -> ❌ LỖI: Không tìm thấy JS confirmOAuthLink trong HTML!")
            
    except Exception as e:
        print("❌ LỖI biên dịch 'register.html':", str(e))
        
    # 2. Kiểm tra base.html
    try:
        template_base = env.get_template("base.html")
        # base.html là template cha, ta mock các block
        context_base = {
            "request": dummy_request,
            "configs": {},
            "active_event_id": 1,
            "logged_in": True,
            "athlete": {"id": 1, "full_name": "Test VĐV", "is_admin": True}
        }
        rendered_base = template_base.render(context_base)
        print("✅ Biên dịch 'base.html': THÀNH CÔNG!")
        
        if "function confirmOAuthLink" in rendered_base:
            print("   -> JS confirmOAuthLink tồn tại trong HTML kết quả!")
        else:
            print("   -> ❌ LỖI: Không tìm thấy JS confirmOAuthLink trong HTML!")
            
    except Exception as e:
        print("❌ LỖI biên dịch 'base.html':", str(e))

if __name__ == "__main__":
    test_template_compilation()
