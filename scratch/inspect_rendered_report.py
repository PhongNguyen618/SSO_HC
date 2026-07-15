"""Inspect the detailed report section in the rendered HTML to see what is generated."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

html_file = "scratch/rendered_admin_inspect.html"
with open(html_file, "r", encoding="utf-8") as f:
    content = f.read()

# Look for 'print-page-break' block
start_idx = content.find('class="print-page-break"')
if start_idx == -1:
    print("❌ print-page-break class NOT found in rendered HTML!")
    sys.exit(1)

print(f"print-page-break found at index {start_idx}")

# Print 3000 characters from start_idx to inspect the structure
print("\n--- FIRST 3000 CHARACTERS OF DETAILED REPORT ---")
print(content[start_idx:start_idx+3000])

print("\n--- CHECKING FOR NO DATA PLACEHOLDERS ---")
placeholders = ["Chưa có dữ liệu", "Chưa có VĐV nào đạt mốc thưởng", "Chưa có dữ liệu phòng ban", "Chưa có dữ liệu tham gia"]
for p in placeholders:
    found = p in content[start_idx:]
    print(f"Contains placeholder '{p}': {found}")
