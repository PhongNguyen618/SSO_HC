import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app
import uuid

def run_tests():
    client = TestClient(app)
    
    unique_sfx_1 = str(uuid.uuid4())[:8]
    unique_sfx_2 = str(uuid.uuid4())[:8]
    unique_sfx_3 = str(uuid.uuid4())[:8]
    
    # Test case 1: SSO member registering for SSO's HC (ID 1) -> Should SUCCESS (303)
    print("\n--- Test Case 1: SSO member registering for SSO's HC ---")
    payload = {
        "full_name": f"Test SSO Athlete {unique_sfx_1}",
        "gender": "Nữ",
        "department": "SSO - CNTT & SCADA",
        "weight": "55.0",
        "strava_name": f"SSO Athlete {unique_sfx_1}",
        "event_id": "1",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 303:
        print("[PASS] Successfully registered SSO member for SSO's HC!")
    else:
        print("[FAIL] Failed to register SSO member!")

    # Test case 2: NSMO member registering for SSO's HC (ID 1) -> Should FAIL (200 with error)
    print("\n--- Test Case 2: NSMO member registering for SSO's HC ---")
    payload = {
        "full_name": f"Test NSMO Athlete {unique_sfx_2}",
        "gender": "Nam",
        "department": "NSMO - CNTT&SCADA",
        "weight": "70.0",
        "strava_name": f"NSMO Athlete {unique_sfx_2}",
        "event_id": "1",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    has_msg = "SSO&#39;s HC" in response.text or "SSO's HC" in response.text
    if response.status_code == 200 and has_msg:
        print("[PASS] Correctly blocked NSMO member from SSO's HC!")
    else:
        print("[FAIL] Failed to block NSMO member!")

    # Test case 3: NSMO member registering for SSO50 (ID 2) -> Should SUCCESS (303)
    print("\n--- Test Case 3: NSMO member registering for SSO50 ---")
    payload = {
        "full_name": f"Test NSMO Athlete {unique_sfx_3}",
        "gender": "Nam",
        "department": "NSMO - CNTT&SCADA",
        "weight": "70.0",
        "strava_name": f"NSMO Athlete {unique_sfx_3}",
        "event_id": "2",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 303:
        print("[PASS] Successfully registered NSMO member for SSO50!")
    else:
        print("[FAIL] Failed to register NSMO member for SSO50!")

if __name__ == "__main__":
    run_tests()
