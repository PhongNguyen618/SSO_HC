"""
Phân tích cú pháp JavaScript bằng cách kiểm tra tính cân bằng của các dấu ngoặc:
'( )', '{ }', '[ ]'.
Script này sẽ bỏ qua các dấu ngoặc nằm trong chuỗi ký tự (string literal)
hoặc comment (dòng đơn // hoặc dòng khối /* */) để tránh nhận diện sai.
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

scratch_dir = os.path.dirname(os.path.abspath(__file__))
js_files = [f for f in os.listdir(scratch_dir) if f.startswith("extracted_") and f.endswith(".js")]

print(f"🔍 Đang phân tích {len(js_files)} file JavaScript trích xuất...\n")

def check_brackets_balance(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()
        
    stack = []
    # Lưu vết vị trí dòng và cột của dấu mở ngoặc để báo cáo chính xác
    line_num = 1
    col_num = 0
    
    in_string = False
    string_char = None
    in_single_comment = False
    in_multi_comment = False
    
    i = 0
    n = len(code)
    
    errors = []
    
    while i < n:
        char = code[i]
        
        # Cập nhật số dòng, số cột
        if char == '\n':
            line_num += 1
            col_num = 0
        else:
            col_num += 1
            
        # 1. Xử lý comment đa dòng /* ... */
        if in_multi_comment:
            if i + 1 < n and char == '*' and code[i+1] == '/':
                in_multi_comment = False
                i += 2
                col_num += 1
                continue
            i += 1
            continue
            
        # 2. Xử lý comment đơn dòng // ...
        if in_single_comment:
            if char == '\n':
                in_single_comment = False
            i += 1
            continue
            
        # 3. Xử lý chuỗi ký tự (String Literals) bao gồm cả Template Literals `...`
        if in_string:
            # Xử lý ký tự escape \ (ví dụ: \', \", \`)
            if char == '\\' and i + 1 < n:
                i += 2
                col_num += 1
                continue
            if char == string_char:
                in_string = False
                string_char = None
            i += 1
            continue
            
        # Bắt đầu comment hoặc Regex literal
        if char == '/' and i + 1 < n:
            if code[i+1] == '/':
                in_single_comment = True
                i += 2
                col_num += 1
                continue
            elif code[i+1] == '*':
                in_multi_comment = True
                i += 2
                col_num += 1
                continue
            else:
                # Kiểm tra xem đây có phải là Regex literal không
                # Trong JS, một Regex literal bắt đầu bằng '/' nếu ký tự trước đó là toán tử, dấu ngoặc mở, hoặc từ khóa
                # Để đơn giản, ta tìm dấu '/' kết thúc trên cùng một dòng và nhảy qua
                # (vì Regex literal không được xuống dòng trừ khi escape)
                j = i + 1
                is_regex = False
                escape = False
                while j < n and code[j] != '\n':
                    if code[j] == '\\':
                        escape = not escape
                        j += 1
                        continue
                    if code[j] == '/' and not escape:
                        is_regex = True
                        break
                    escape = False
                    j += 1
                
                if is_regex:
                    # Nhảy qua toàn bộ regex literal bao gồm cả flags (ví dụ: /pattern/gim)
                    i = j + 1
                    col_num += (j - i)
                    # Bỏ qua các flag chữ cái tiếp sau
                    while i < n and code[i].isalpha():
                        i += 1
                        col_num += 1
                    continue

                
        # Bắt đầu chuỗi
        if char in ['"', "'", '`']:
            in_string = True
            string_char = char
            i += 1
            continue
            
        # Xử lý các dấu ngoặc
        if char in ['(', '{', '[']:
            stack.append((char, line_num, col_num))
        elif char in [')', '}', ']']:
            if not stack:
                errors.append(f"  ❌ Phát hiện dấu đóng '{char}' thừa tại Dòng {line_num}, Cột {col_num}")
            else:
                top_char, top_line, top_col = stack.pop()
                # Kiểm tra khớp cặp
                if char == ')' and top_char != '(':
                    errors.append(f"  ❌ Sai khớp cặp: Mở '{top_char}' tại Dòng {top_line} nhưng lại Đóng '{char}' tại Dòng {line_num}")
                elif char == '}' and top_char != '{':
                    errors.append(f"  ❌ Sai khớp cặp: Mở '{top_char}' tại Dòng {top_line} nhưng lại Đóng '{char}' tại Dòng {line_num}")
                elif char == ']' and top_char != '[':
                    errors.append(f"  ❌ Sai khớp cặp: Mở '{top_char}' tại Dòng {top_line} nhưng lại Đóng '{char}' tại Dòng {line_num}")
                    
        i += 1
        
    # Kiểm tra xem còn dấu mở ngoặc nào chưa được đóng không
    while stack:
        char, line, col = stack.pop()
        errors.append(f"  ❌ Dấu mở '{char}' tại Dòng {line}, Cột {col} KHÔNG được đóng!")
        
    return errors

all_ok = True
for f in sorted(js_files):
    fpath = os.path.join(scratch_dir, f)
    errors = check_brackets_balance(fpath)
    if errors:
        all_ok = False
        print(f"📁 File: scratch/{f}")
        for err in errors[:5]:  # Chỉ hiện tối đa 5 lỗi đầu tiên
            print(err)
        print()
    else:
        # print(f"  ✅ scratch/{f} - OK")
        pass

if all_ok:
    print("🎉 Tất cả các file JS đều có cấu trúc dấu ngoặc hoàn toàn CÂN BẰNG! Không phát hiện lỗi thiếu dấu đóng ngoặc nào.")
else:
    print("🚨 Phát hiện một số file có lỗi dấu ngoặc! Vui lòng kiểm tra kỹ các file báo đỏ ở trên.")
    sys.exit(1)
