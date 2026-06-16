import re
from collections import Counter

with open("templates/admin.html", "r", encoding="utf-8") as f:
    content = f.read()

# Find all function declarations: function name(...)
funcs = re.findall(r"function\s+(\w+)\s*\(", content)
counter = Counter(funcs)

print("JS Function declarations and count:")
has_duplicate = False
for fn, count in counter.most_common():
    if count > 1:
        print(f"  [DUPLICATE] {fn}: {count} times")
        has_duplicate = True

if not has_duplicate:
    print("No duplicates found!")
print("Check completed.")
