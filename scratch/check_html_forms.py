import os
import re

def check_forms():
    templates_dir = "templates"
    for filename in os.listdir(templates_dir):
        if filename.endswith(".html"):
            filepath = os.path.join(templates_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Simple count of <form and </form
            # Remove comments to avoid false matches
            content_clean = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
            content_clean = re.sub(r"{#.*?#}", "", content_clean, flags=re.DOTALL)
            
            opens = len(re.findall(r"<form\b", content_clean, re.IGNORECASE))
            closes = len(re.findall(r"</form\b", content_clean, re.IGNORECASE))
            
            print(f"File: {filename} | <form opens: {opens} | </form closes: {closes}")
            if opens != closes:
                print(f"  [WARNING] Mismatched form tags in {filename}!")

if __name__ == "__main__":
    check_forms()
