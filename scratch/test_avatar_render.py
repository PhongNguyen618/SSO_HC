import sys
from jinja2 import Environment, FileSystemLoader

class MockURL:
    path = '/avatar'

class MockRequest:
    url = MockURL()

try:
    env = Environment(loader=FileSystemLoader('templates'))
    
    # Mock hàm get_configs toàn cục
    def mock_get_configs():
        return {
            "global_avatar_frame": "/static/uploads/frame.png",
            "rules_title": "Thể lệ giải chạy",
            "rules_banner_image": "/branding/BANNER.png",
            "rules_banner_text": "Chào mừng..."
        }
    
    env.globals['get_configs'] = mock_get_configs
    
    template = env.get_template('avatar.html')
    
    # Mock data tương tự như route /avatar trả về
    mock_context = {
        "request": MockRequest(),
        "configs": mock_get_configs(),
        "all_athletes": [
            {"id": 1, "full_name": "Nguyễn Văn A", "department": "Phòng Kỹ Thuật"},
            {"id": 2, "full_name": "Trần Thị B", "department": "Phòng Nhân Sự"}
        ],
        "avatar_frame_url": "/static/uploads/frame.png?t=12345678"
    }
    
    # Render thử sang chuỗi HTML
    rendered_html = template.render(mock_context)
    print("SUCCESS: avatar.html rendered successfully without syntax errors!")
    print(f"Rendered size: {len(rendered_html)} bytes")
except Exception as e:
    print(f"FAILED to render avatar.html: {e}")
    sys.exit(1)
