import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app
import uuid

def run_tests():
    client = TestClient(app)
    
    unique_sfx_1 = str(uuid.uuid4())[:8]
    unique_sfx_2 = str(uuid.uuid4())[:8]
    
    # 1. SSO member registering for SSO's HC (ID 1) -> Should SUCCESS (303)
    print("\n--- Test Case 1: SSO member registering for SSO's HC (ID 1) ---")
    payload = {
        "full_name": f"SSO Member One {unique_sfx_1}",
        "gender": "Nữ",
        "department": "SSO - KẾ HOẠCH",
        "weight": "55.0",
        "strava_name": f"sso.one.{unique_sfx_1}",
        "event_id": "1",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 303:
        print("[PASS] SSO member registered for SSO's HC successfully!")
    else:
        print("[FAIL] SSO member blocked from SSO's HC!")

    # 2. SSO member registering for SSO50 (ID 2) -> Should SUCCESS (303)
    print("\n--- Test Case 2: SSO member registering for SSO50 (ID 2) ---")
    payload = {
        "full_name": f"SSO Member Two {unique_sfx_2}",
        "gender": "Nam",
        "department": "SSO - PHƯƠNG THỨC",
        "weight": "68.0",
        "strava_name": f"sso.two.{unique_sfx_2}",
        "event_id": "2",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 303:
        print("[PASS] SSO member registered for SSO50 successfully!")
    else:
        print("[FAIL] SSO member blocked from SSO50!")

if __name__ == "__main__":
    run_tests()
