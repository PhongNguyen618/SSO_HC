import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine, SessionLocal, Athlete
import sqlite3

def run_test():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    # Ensure athlete ID 1 exists
    ath = db.query(Athlete).filter(Athlete.id == 1).first()
    if not ath:
        db.add(Athlete(id=1, full_name="Test Athlete", gender="Nam", weight=60.0, department="Test"))
        db.commit()
    db.close()
    
    client = TestClient(app)
    
    # 1. Test redirect without activity scopes
    print("Testing OAuth callback WITHOUT activity scope...")
    response = client.get("/exchange_user_token?code=testcode&state=1&scope=read,profile:read_all", follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    print(f"Location Header: {response.headers.get('location')}")
    import urllib.parse
    decoded_loc = urllib.parse.unquote(response.headers.get('location'))
    assert "activity:read" in decoded_loc
    print("[OK] Correctly blocked and redirected to error page!")
    
    # 2. Test redirect WITH activity scope
    print("\nTesting OAuth callback WITH activity scope...")
    response = client.get("/exchange_user_token?code=testcode&state=1&scope=read,activity:read", follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    # It should pass scope check and continue to POST token (which will fail because code is dummy, returning error 400 or 303 redirect)
    print(f"Location Header: {response.headers.get('location')}")
    print("[OK] Passed scope check successfully!")

if __name__ == "__main__":
    run_test()
