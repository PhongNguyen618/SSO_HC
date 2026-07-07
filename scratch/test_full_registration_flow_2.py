import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app
import uuid

def run_tests():
    client = TestClient(app)
    
    unique_sfx_1 = str(uuid.uuid4())[:8]
    unique_sfx_2 = str(uuid.uuid4())[:8]
    
    # Test case 1: NSMO prefix -> Should SUCCEED (redirect to Strava 303)
    print("\n--- Test Case 1: NSMO department registering for SSO's HC ---")
    payload = {
        "full_name": f"Test NSMO Athlete {unique_sfx_1}",
        "gender": "Nữ",
        "department": "NSMO - CNTT&SCADA",
        "weight": "55.0",
        "strava_name": f"NSMO Athlete {unique_sfx_1}",
        "event_id": "1",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 303:
        print("[PASS] Successfully registered NSMO member!")
    else:
        print("[FAIL] Failed to register NSMO member!")
        
    # Test case 2: CSO prefix -> Should SUCCEED (redirect to Strava 303)
    print("\n--- Test Case 2: CSO department registering for SSO's HC ---")
    payload = {
        "full_name": f"Test CSO Athlete {unique_sfx_2}",
        "gender": "Nam",
        "department": "CSO - ĐIỀU ĐỘ",
        "weight": "70.0",
        "strava_name": f"CSO Athlete {unique_sfx_2}",
        "event_id": "1",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 303:
        print("[PASS] Successfully registered CSO member!")
    else:
        print("[FAIL] Failed to register CSO member!")

if __name__ == "__main__":
    run_tests()
