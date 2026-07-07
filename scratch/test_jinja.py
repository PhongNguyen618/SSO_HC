import jinja2
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    template_env = jinja2.Environment(loader=template_loader)
    
    # Thử load template profile.html
    template = template_env.get_template("profile.html")
    print("Kiểm tra cú pháp Jinja template profile.html: HOÀN TOÀN HỢP LỆ! ✅")
except Exception as e:
    print(f"Lỗi cú pháp Jinja trong template: {e}")
    sys.exit(1)
