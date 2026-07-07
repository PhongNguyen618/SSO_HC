"""Test dong bo thu cong va kiem tra scheduler."""
import sys, os
sys.path.insert(0, os.getcwd())

# 1. Test sync_club_activities truc tiep
print("=" * 60)
print("TEST 1: sync_club_activities() - Dong bo thu cong")
print("=" * 60)
try:
    from backend.sync_engine import sync_club_activities
    res = sync_club_activities()
    print(f"  Status:  {res.get('status')}")
    print(f"  New:     {res.get('new_activities')}")
    print(f"  Error:   {res.get('error')}")
    if res.get('details'):
        for d in res['details']:
            print(f"    Event: {d.get('event')}, Status: {d.get('status')}, New: {d.get('new', 0)}, Error: {d.get('error', '-')}")
    print("  >> KET QUA: OK" if res.get('status') in ('success', 'partial') else f"  >> KET QUA: LOI - {res.get('error')}")
except Exception as e:
    print(f"  >> EXCEPTION: {e}")
    import traceback
    traceback.print_exc()

# 2. Test trigger_sync route (giong nhu admin bam nut)
print()
print("=" * 60)
print("TEST 2: /admin/sync route - Mo phong click dong bo")
print("=" * 60)
try:
    from fastapi.testclient import TestClient
    from backend.main import app
    
    client = TestClient(app)
    
    # Dang nhap admin truoc
    login_resp = client.post("/admin/login", data={"username": "admin", "password": "admin"}, follow_redirects=False)
    print(f"  Login status: {login_resp.status_code}")
    cookies = login_resp.cookies
    
    # Goi dong bo thu cong
    sync_resp = client.post("/admin/sync", cookies=cookies)
    print(f"  Sync status code: {sync_resp.status_code}")
    if sync_resp.status_code == 200:
        data = sync_resp.json()
        print(f"  Response: {data}")
        print(f"  >> KET QUA: OK")
    else:
        print(f"  Response text: {sync_resp.text[:500]}")
        print(f"  >> KET QUA: LOI HTTP {sync_resp.status_code}")
except Exception as e:
    print(f"  >> EXCEPTION: {e}")
    import traceback
    traceback.print_exc()

# 3. Kiem tra scheduler
print()
print("=" * 60)
print("TEST 3: Kiem tra scheduler config")
print("=" * 60)
try:
    from backend.database import SessionLocal, Config
    db = SessionLocal()
    interval = db.query(Config).filter(Config.key == "sync_interval_hours").first()
    print(f"  sync_interval_hours: {interval.value if interval else 'NOT SET (default 1h)'}")
    
    # Kiem tra strava credentials
    keys = ["strava_client_id", "strava_client_secret", "strava_refresh_token", "strava_access_token", "strava_expires_at"]
    for k in keys:
        c = db.query(Config).filter(Config.key == k).first()
        val = c.value if c else "NOT SET"
        # An bot token
        if val and len(val) > 10 and k != "strava_expires_at":
            val = val[:6] + "..." + val[-4:]
        print(f"  {k}: {val}")
    db.close()
    print(f"  >> KET QUA: OK")
except Exception as e:
    print(f"  >> EXCEPTION: {e}")
    import traceback
    traceback.print_exc()
