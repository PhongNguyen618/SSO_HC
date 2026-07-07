import sys, os
sys.path.insert(0, os.getcwd())
from backend.database import SessionLocal, Config, CompetitionEvent
db = SessionLocal()

# Check strava_club_id in config
c = db.query(Config).filter(Config.key == "strava_club_id").first()
print("Config strava_club_id:", c.value if c else "NOT SET")

# Check each active competition
events = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).all()
print(f"Active events: {len(events)}")
for ev in events:
    print(f"  Event {ev.id}: club_id={ev.strava_club_id}, active={ev.is_active}")

# Check credentials
keys = ["strava_client_id", "strava_client_secret", "strava_refresh_token", "strava_access_token", "strava_expires_at"]
print()
print("Strava credentials:")
for k in keys:
    c = db.query(Config).filter(Config.key == k).first()
    val = c.value if c else None
    if not val or val.strip() == "":
        print(f"  {k}: ** EMPTY **")
    elif k == "strava_expires_at":
        print(f"  {k}: {val}")
    else:
        print(f"  {k}: {val[:4]}...{val[-3:]} (len={len(val)})")

db.close()
