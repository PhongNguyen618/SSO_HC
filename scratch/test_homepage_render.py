import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app

def test_homepage():
    client = TestClient(app)
    try:
        response = client.get("/")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("[OK] Homepage rendered successfully!")
        else:
            print(f"[ERROR] Homepage returned status code {response.status_code}")
            print(response.text[:500])
    except Exception as e:
        print(f"[EXCEPTION] Failed to render homepage: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_homepage()
