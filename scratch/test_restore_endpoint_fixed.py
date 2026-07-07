import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine, SessionLocal, Config
import sqlite3
import os

def run_test():
    # Initialize SQLite database schema
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    # Add configs for authentication
    db.merge(Config(key='admin_session_id', value='test_session_token'))
    db.merge(Config(key='admin_session_expiry', value='9999999999'))
    db.merge(Config(key='admin_username', value='admin'))
    db.commit()
    db.close()
    
    client = TestClient(app)
    client.cookies.set("sso_hc_admin_session", "test_session_token")
    
    print("Testing restore endpoint POST `/admin/restore-backup-data`...")
    response = client.post("/admin/restore-backup-data")
    print(f"Status Code: {response.status_code}")
    print(f"JSON Response: {response.text.encode('ascii', 'ignore').decode('ascii')}")

if __name__ == "__main__":
    run_test()
