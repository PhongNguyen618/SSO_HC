"""Find all HTML tags using color variables in the rendered HTML."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import re

html_file = "scratch/rendered_admin_inspect.html"
with open(html_file, "r", encoding="utf-8") as f:
    content = f.read()

# Match style="...color: var(...)..." or style="...color:var(...)..."
# We'll print the tag and the style value
matches = re.finditer(r'<([a-z0-9]+)[^>]*style="([^"]*color\s*:\s*var\([^)]+\)[^"]*)"[^>]*>', content, re.IGNORECASE)

print("Listing all tags in rendered HTML that use color variables:")
count = 0
for match in matches:
    tag = match.group(1)
    style = match.group(2)
    # Check if this tag is inside the print-page-break block (index ~59642 to end)
    is_in_report = match.start() >= 59642
    if is_in_report:
        count += 1
        print(f"- Index {match.start()}: <{tag}> -> Style: {style}")

print(f"Total found in detailed report: {count}")
