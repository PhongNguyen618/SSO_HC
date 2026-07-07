import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app
import sqlite3

def run_all_registration_tests():
    client = TestClient(app)
    
    # Test cases:
    # 1. SSO's HC (ID 1), department "SSO - CNTT" -> Should SUCCEED (redirect to Strava OAuth)
    print("\n--- Test Case 1: SSO member registering for SSO's HC (ID 1) ---")
    payload = {
        "full_name": "Test Athlete One",
        "gender": "Nữ",
        "department": "SSO - CNTT & SCADA",
        "weight": "55.0",
        "strava_name": "Test Athlete One Strava",
        "event_id": "1",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 303:
        print("[PASS] Successfully redirected to Strava!")
    else:
        print("[FAIL] Failed to register!")
        
    # 2. SSO's HC (ID 1), department "CÔNG TY NHIỆT ĐIỆN PHÚ MỸ" -> Should FAIL (validation block)
    print("\n--- Test Case 2: Non-SSO member registering for SSO's HC (ID 1) ---")
    payload = {
        "full_name": "Test Athlete Two",
        "gender": "Nam",
        "department": "CÔNG TY NHIỆT ĐIỆN PHÚ MỸ",
        "weight": "70.0",
        "strava_name": "Test Athlete Two Strava",
        "event_id": "1",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    has_msg = "SSO&#39;s HC" in response.text or "SSO's HC" in response.text
    if response.status_code == 200 and has_msg:
        print("[PASS] Correctly blocked non-SSO member!")
    else:
        print("[FAIL] Failed to block or error didn't show!")
        
    # 3. SSO50 (ID 2), department "CÔNG TY NHIỆT ĐIỆN PHÚ MỸ" -> Should SUCCEED (redirect to Strava OAuth)
    print("\n--- Test Case 3: Non-SSO member registering for Event ID 2 ---")
    payload = {
        "full_name": "Test Athlete Three",
        "gender": "Nam",
        "department": "CÔNG TY NHIỆT ĐIỆN PHÚ MỸ",
        "weight": "70.0",
        "strava_name": "Test Athlete Three Strava",
        "event_id": "2",
        "is_update": "false"
    }
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 303:
        print("[PASS] Successfully registered non-SSO member for Event ID 2!")
    else:
        print("[FAIL] Failed to register!")

if __name__ == "__main__":
    run_all_registration_tests()
