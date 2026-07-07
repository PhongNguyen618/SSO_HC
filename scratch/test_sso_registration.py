import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app

def test_sso_restriction():
    client = TestClient(app)
    
    # 1. Thử đăng ký giải SSO's HC (ID 1) với phòng ban không phải SSO (ví dụ: PHÚ MỸ)
    print("Testing registration to SSO's HC (ID 1) with non-SSO department...")
    payload = {
        "full_name": "Nguyen Van NonSSO",
        "gender": "Nam",
        "department": "CÔNG TY NHIỆT ĐIỆN PHÚ MỸ",
        "weight": "65.0",
        "strava_name": "Van NonSSO",
        "event_id": "1", # SSO's HC
        "is_update": "false"
    }
    response = client.post("/register", data=payload)
    if "Giải đấu SSO's HC là giải đấu nội bộ" in response.text:
        print("[OK] Correctly blocked non-SSO registration on backend!")
    else:
        print("[FAIL] Did not block registration!")
        print(response.text[:1000])

    # 2. Thử đăng ký giải SSO's HC (ID 1) với phòng ban thuộc SSO (ví dụ: SSO - CNTT)
    print("\nTesting registration to SSO's HC (ID 1) with SSO department...")
    payload = {
        "full_name": "Nguyen Van SSO",
        "gender": "Nam",
        "department": "SSO - CNTT & SCADA",
        "weight": "65.0",
        "strava_name": "Van SSO Test",
        "event_id": "1", # SSO's HC
        "is_update": "false"
    }
    # We expect a redirect to Strava OAuth if successful (status code 303 or 200 with redirect link)
    response = client.post("/register", data=payload, follow_redirects=False)
    print(f"Response status code: {response.status_code}")
    if response.status_code == 303:
        print("[OK] Correctly redirected to Strava OAuth for SSO member!")
        print(f"Redirect target: {response.headers.get('location')}")
    else:
        print("[FAIL] Failed to register SSO member!")
        print(response.text[:1000])

if __name__ == "__main__":
    test_sso_restriction()
