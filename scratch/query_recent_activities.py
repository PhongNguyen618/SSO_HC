import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import SessionLocal, Athlete, Activity

db = SessionLocal()
try:
    activities = db.query(Activity).order_by(Activity.sync_date.desc()).limit(10).all()
    print("Top 10 recent synchronized activities in DB:")
    for act in activities:
        ath = db.query(Athlete).filter(Athlete.id == act.athlete_id).first()
        ath_name = ath.full_name if ath else act.athlete_name_raw
        print(f"SyncDate: {act.sync_date} | Athlete: {ath_name} | Date: {act.activity_date} | Name: '{act.name}' | Dist: {act.distance_km}km | EventID: {act.event_id}")
finally:
    db.close()
