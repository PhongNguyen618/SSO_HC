import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from fastapi.testclient import TestClient
from backend.main import app
import sqlite3

def run_test():
    client = TestClient(app)
    
    conn = sqlite3.connect("SSO_HC.db")
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM competition_events")
    events = cur.fetchall()
    print("Events in active DB count:", len(events))
    for ev in events:
        print(f"  Event ID: {ev[0]}, Title: {ev[1].encode('ascii', 'ignore').decode('ascii')}")
    conn.close()
    
    payload = {
        "full_name": "Nguyen Van NonSSO",
        "gender": "Nam",
        "department": "CONG TY NHIET DIEN PHU MY",
        "weight": "65.0",
        "strava_name": "Van NonSSO",
        "event_id": "1",
        "is_update": "false"
    }
    response = client.post("/register", data=payload)
    print("Response Status Code:", response.status_code)
    
    # Check if the block message is in the response text
    has_message = "SSO's HC" in response.text and "noi bo" in response.text.encode('ascii', 'ignore').decode('ascii')
    print("Has block message:", "SSO's HC" in response.text)
    
    # Let's write the response to a file so we can view it
    with open("scratch/test_response.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Saved response to scratch/test_response.html")

if __name__ == "__main__":
    run_test()
