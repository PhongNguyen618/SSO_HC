import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app
import sqlite3

def run_test():
    client = TestClient(app)
    
    # Check events in DB
    conn = sqlite3.connect("SSO_HC.db")
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM competition_events")
    print("Events in active DB:", cur.fetchall())
    conn.close()
    
    payload = {
        "full_name": "Nguyen Van NonSSO",
        "gender": "Nam",
        "department": "CÔNG TY NHIỆT ĐIỆN PHÚ MỸ",
        "weight": "65.0",
        "strava_name": "Van NonSSO",
        "event_id": "1",
        "is_update": "false"
    }
    response = client.post("/register", data=payload)
    print("Response Status Code:", response.status_code)
    
    # Check if the block message is in the response text
    has_message = "Giải đấu SSO's HC là giải đấu nội bộ" in response.text
    print("Has block message:", has_message)

if __name__ == "__main__":
    run_test()
