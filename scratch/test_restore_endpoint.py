import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app
import sqlite3

def run_test():
    client = TestClient(app)
    
    # 1. Login to get a valid admin session cookie
    conn = sqlite3.connect("SSO_HC.db")
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO configs (key, value) VALUES ('admin_session_id', 'test_session_token')")
    cur.execute("INSERT OR REPLACE INTO configs (key, value) VALUES ('admin_session_expiry', '9999999999')")
    cur.execute("INSERT OR REPLACE INTO configs (key, value) VALUES ('admin_username', 'admin')")
    conn.commit()
    conn.close()
    
    client.cookies.set("sso_hc_admin_session", "test_session_token")
    
    print("Testing restore endpoint POST `/admin/restore-backup-data`...")
    response = client.post("/admin/restore-backup-data")
    print(f"Status Code: {response.status_code}")
    print(f"JSON Response: {response.text.encode('ascii', 'ignore').decode('ascii')}")

if __name__ == "__main__":
    run_test()
