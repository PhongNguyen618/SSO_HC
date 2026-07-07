"""Kiểm tra cú pháp Jinja2 của tất cả template files."""
import os
import sys
import io
from jinja2 import Environment, FileSystemLoader

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
env = Environment(loader=FileSystemLoader(templates_dir))

# Đăng ký mock globals giống backend thật
env.globals['get_configs'] = lambda *args, **kwargs: {}
env.globals['get_admin_session'] = lambda *args, **kwargs: None
env.globals['url_for'] = lambda name, **kwargs: f"/static/{kwargs.get('filename', '')}"

# Mock filter
env.filters['currency'] = lambda v: f"{v} VND"

template_files = [f for f in os.listdir(templates_dir) if f.endswith('.html')]

print(f"📂 Kiểm tra {len(template_files)} template files trong: {templates_dir}\n")

errors = []
for fname in sorted(template_files):
    try:
        # Chỉ parse (compile) template, không render
        # Nếu có lỗi cú pháp Jinja sẽ bị phát hiện ngay
        tmpl = env.get_template(fname)
        print(f"  ✅ {fname} - OK (compiled successfully)")
    except Exception as e:
        print(f"  ❌ {fname} - LỖI: {e}")
        errors.append((fname, str(e)))

print()
if errors:
    print(f"🚨 Phát hiện {len(errors)} lỗi cú pháp!")
    for fname, err in errors:
        print(f"  - {fname}: {err}")
    sys.exit(1)
else:
    print(f"✅ Tất cả {len(template_files)} template files đều không có lỗi cú pháp Jinja2!")
    print("🎉 An toàn để deploy lên VPS.")
