import requests, sys, io, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
from backend.database import SessionLocal, Config

db = SessionLocal()
admin_session_id = db.query(Config).filter(Config.key == "admin_session_id").first()
db.close()

s = requests.Session()
s.cookies.set("sso_hc_admin_session", admin_session_id.value)

r = s.get("http://127.0.0.1:8000/admin", timeout=30)
print(f"Status: {r.status_code}, Length: {len(r.text)}")
print(f"tab-analytics: {'tab-analytics' in r.text}")
print(f"statsData present: {'const statsData' in r.text}")
print(f"Server error: {'Internal Server Error' in r.text or 'Traceback' in r.text}")

if 'const statsData' in r.text:
    idx = r.text.find('const statsData')
    snippet = r.text[idx:idx+50]
    if 'null' in snippet:
        print("statsData is null (not logged in)")
    else:
        print("statsData has data!")

# Check JS bracket balance in rendered page
scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
for i, script in enumerate(scripts):
    if len(script) > 1000:
        co = script.count('{')
        cc = script.count('}')
        po = script.count('(')
        pc = script.count(')')
        balanced = co == cc and po == pc
        print(f"Script #{i+1} ({len(script)} chars): {'OK' if balanced else 'IMBALANCED'} curly={co}/{cc} paren={po}/{pc}")
