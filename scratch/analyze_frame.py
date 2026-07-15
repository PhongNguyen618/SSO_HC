"""Analyze rendered HTML using Python standard libraries only to find color styles in print mode."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import re

html_file = "scratch/rendered_admin_inspect.html"
with open(html_file, "r", encoding="utf-8") as f:
    content = f.read()

# Find the content inside class="print-page-break"
# The print-page-break div starts at `<div class="print-page-break"` and goes until the end of tab-analytics (or next div).
# We can find all tags with style attributes inside it.
matches = re.findall(r'<([a-z0-9]+)[^>]*style="([^"]*)"[^>]*>([^<]*)', content, re.IGNORECASE)

print(f"Analyzing all style attributes in the rendered page:")
for tag, style, text in matches:
    if "color" in style.lower():
        # Check if this belongs to print-page-break (we can just print everything and manually filter)
        text_clean = text.strip()[:30]
        # Ignore tabs that are hidden
        if "tab-config" in content[content.find(style)-200:content.find(style)]:
            continue
        print(f"<{tag}> '{text_clean}' -> Style: {style}")
