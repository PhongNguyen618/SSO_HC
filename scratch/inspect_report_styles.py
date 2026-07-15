"""Search for tags with style attributes in the first 80,000 characters of the detailed report."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import re

html_file = "scratch/rendered_admin_inspect.html"
with open(html_file, "r", encoding="utf-8") as f:
    content = f.read()

# Start from index 59642 (detailed report start)
report_content = content[59642:150000]

print("Scanning detailed report (indices 59642 to 150000) for color styling:")
# Find all occurrences of "color:" inside style attributes
matches = re.finditer(r'<([a-z0-9]+)[^>]*style="([^"]*color\s*:\s*[^;"]+;?[^"]*)"[^>]*>([^<]*)', report_content, re.IGNORECASE)

count = 0
for m in matches:
    count += 1
    print(f"{count}. <{m.group(1)}> '{m.group(3).strip()[:30]}' -> Style: {m.group(2)}")
