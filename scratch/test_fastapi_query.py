import uvicorn
from fastapi import FastAPI, Query
import urllib.request
import urllib.error
import threading
import time

app = FastAPI()

@app.get("/register")
def register(event_id: int = None):
    return {"event_id": event_id}

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8099, log_level="error")

# Start server in background thread
t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(1) # wait for server to start

# Test with no event_id
try:
    with urllib.request.urlopen("http://127.0.0.1:8099/register") as response:
        print("GET /register:", response.read().decode())
except urllib.error.HTTPError as e:
    print("GET /register HTTPError:", e.code, e.read().decode())

# Test with event_id=
try:
    with urllib.request.urlopen("http://127.0.0.1:8099/register?event_id=") as response:
        print("GET /register?event_id=:", response.read().decode())
except urllib.error.HTTPError as e:
    print("GET /register?event_id= HTTPError:", e.code, e.read().decode())
