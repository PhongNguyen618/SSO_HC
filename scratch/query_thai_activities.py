import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import SessionLocal, Athlete, Activity

db = SessionLocal()
try:
    athlete = db.query(Athlete).filter(Athlete.full_name.like("%Thái%")).first()
    if athlete:
        print(f"Athlete found: {athlete.full_name} (ID: {athlete.id})")
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.activity_date == "2026-06-26"
        ).all()
        print(f"Found {len(activities)} activities for date 2026-06-26:")
        for act in activities:
            print(f"ID: {act.id[:10]}... Name: '{act.name}' Sport: {act.sport_type} Dist: {act.distance_km}km (Raw: {act.distance_km_raw}) Time: {act.moving_time_min}min Date: {act.activity_date}")
    else:
        print("Athlete Lê Văn Thái not found in DB.")
finally:
    db.close()
