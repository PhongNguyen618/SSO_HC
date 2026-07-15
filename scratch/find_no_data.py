"""Find lines with 'Chưa có dữ liệu' in the rendered HTML."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

html_file = "scratch/rendered_admin_inspect.html"
with open(html_file, "r", encoding="utf-8") as f:
    content = f.read()

# Find all occurrences and print context
import re
for match in re.finditer(r'Chưa có dữ liệu', content):
    start = max(0, match.start() - 150)
    end = min(len(content), match.end() + 150)
    print(f"Occurrence at index {match.start()}:\n{content[start:end]}\n{'-'*50}")
