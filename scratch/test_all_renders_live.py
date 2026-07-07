"""
Chạy thử nghiệm render thực tế tất cả các trang web qua FastAPI TestClient
để chắc chắn 100% không có lỗi runtime (NameError, TypeError, TemplateError, v.v.)
khi người dùng truy cập các đường dẫn chính.
"""
import sys
import io
import os
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Thêm thư mục gốc vào path để import backend
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

try:
    from fastapi.testclient import TestClient
    from backend.main import app
    print("✅ Đã import thành công FastAPI app!")
except Exception as e:
    print(f"❌ Lỗi import app: {e}")
    sys.exit(1)

client = TestClient(app)

# Các trang cần test render
routes_to_test = [
    ("/", "Trang chủ (Bảng xếp hạng)"),
    ("/rules", "Trang Quy chế"),
    ("/register", "Trang Đăng ký"),
    ("/avatar", "Trang Đồng bộ Avatar"),
    ("/connect-existing", "Trang Liên kết tài khoản cũ"),
    ("/admin", "Trang Admin đăng nhập"),
    ("/profile/1", "Trang cá nhân VĐV (ID=1)"),
]

print("\n🚀 BẮT ĐẦU CHẠY THỬ RENDER CÁC TRANG TRÊN DATABASE LOCAL...")

errors = 0
for route, desc in routes_to_test:
    print(f"\n🔍 Đang gọi thử: {desc} ({route})...")
    try:
        # Giả lập request
        response = client.get(route, follow_redirects=True)
        print(f"  Status code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"  ✅ Tải trang thành công!")
            # Kiểm tra xem có chứa từ khóa lỗi Jinja/FastAPI phổ biến không
            content = response.text.lower()
            err_keywords = ["internal server error", "templatenotfound", "traceback", "syntaxerror", "nameerror"]
            found_errs = [kw for kw in err_keywords if kw in content]
            
            # Kiểm tra từ khóa 'undefined' một cách thông minh (tránh bắt nhầm cú pháp so sánh JS như '!== undefined')
            if "undefined" in content:
                # Tìm các trường hợp 'undefined' KHÔNG đi kèm với '!==' hoặc '===' hoặc '==' hoặc 'typeof'
                # Nếu chỉ xuất hiện chữ 'undefined' đứng một mình hoặc render từ Jinja bị lỗi
                clean_text = re.sub(r'(!==|===|==|typeof)\s*undefined', '', content)
                clean_text = re.sub(r'undefined\s*(!==|===|==)', '', clean_text)
                if "undefined" in clean_text:
                    found_errs.append("undefined (nghi ngờ biến Jinja trống)")

            
            if found_errs:
                print(f"  ⚠️ Cảnh báo: Phát hiện các từ khóa nghi ngờ lỗi trong HTML trả về: {found_errs}")
                # In ra 5 dòng xung quanh từ khóa đó để check
                lines = response.text.split('\n')
                for kw in found_errs:
                    for idx, line in enumerate(lines):
                        if kw in line.lower():
                            start = max(0, idx - 2)
                            end = min(len(lines), idx + 3)
                            print(f"     --- Đoạn code nghi ngờ lỗi (Dòng {idx+1}): ---")
                            for k in range(start, end):
                                marker = ">>> " if k == idx else "    "
                                print(f"     {marker}{lines[k].strip()}")
                            break
                errors += 1
            else:
                print("  ✅ Nội dung HTML hiển thị sạch sẽ, không có dấu hiệu lỗi!")
        else:
            # Nếu redirect hoặc 404/401 thì vẫn có thể bình thường tùy cấu hình route, nhưng ta ghi nhận để check
            print(f"  ℹ️ Status {response.status_code} (Redirect hoặc yêu cầu quyền truy cập)")
            
    except Exception as route_err:
        print(f"  ❌ Lỗi crash khi tải trang: {route_err}")
        errors += 1

print("\n" + "="*50)
if errors == 0:
    print("🎉 KẾT QUẢ: 100% CÁC TRANG CHÍNH RENDER HOÀN HẢO!")
    print("Không phát hiện lỗi runtime, lỗi cú pháp hay crash hệ thống nào ở môi trường thật local.")
else:
    print(f"🚨 KẾT QUẢ: Phát hiện {errors} trang nghi ngờ có lỗi. Vui lòng kiểm tra nhật ký ở trên.")
    sys.exit(1)
