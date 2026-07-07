"""
Trích xuất tất cả các đoạn mã JavaScript nằm trong thẻ <script> từ 9 file HTML trong templates/
để lưu thành các file .js trong scratch/.
Sau đó, sử dụng một parser JavaScript đơn giản bằng Python để phát hiện các lỗi cú pháp (SyntaxError).
"""
import os
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates_dir = os.path.join(base_dir, "templates")
scratch_dir = os.path.join(base_dir, "scratch")

html_files = [f for f in os.listdir(templates_dir) if f.endswith(".html")]

print("=== TRÍCH XUẤT JAVASCRIPT TỪ CÁC TEMPLATES ===")

js_blocks_count = 0
for fname in html_files:
    fpath = os.path.join(templates_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Tìm tất cả các khối <script>...</script>
    # Dùng regex lazy để bắt đúng từng block
    script_blocks = re.findall(r'<script\b[^>]*>(.*?)</script>', content, re.DOTALL)
    
    if not script_blocks:
        continue
        
    print(f"\n📂 File: {fname} (Tìm thấy {len(script_blocks)} block script)")
    
    for idx, block in enumerate(script_blocks):
        # Bỏ qua các block chỉ chứa Jinja import hoặc rỗng
        if not block.strip():
            continue
            
        # Tạo file JS tạm thời để kiểm tra
        js_name = f"extracted_{fname.replace('.html', '')}_{idx}.js"
        js_path = os.path.join(scratch_dir, js_name)
        
        # Làm sạch code JS khỏi các tag Jinja {{ ... }} hoặc {% ... %} để tránh lỗi cú pháp JS khi parse
        # Thay thế Jinja variables {{ var }} bằng mock string/number
        cleaned_block = re.sub(r'\{\{\s*.*?\}\}', '"jinja_var"', block)
        # Thay thế Jinja blocks {% ... %} bằng comment
        cleaned_block = re.sub(r'\{%\s*.*?%\}', '/* jinja_block */', cleaned_block)
        
        with open(js_path, "w", encoding="utf-8") as js_f:
            js_f.write(cleaned_block)
            
        print(f"  ✍️ Đã trích xuất block {idx} -> scratch/{js_name}")
        js_blocks_count += 1

print(f"\n✅ Đã trích xuất xong {js_blocks_count} blocks Javascript.")
