import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import SessionLocal, Activity

db = SessionLocal()
try:
    total = db.query(Activity).count()
    has_time = db.query(Activity).filter(Activity.activity_time != None, Activity.activity_time != '').count()
    print(f"Total activities in live DB: {total}")
    print(f"Activities with activity_time: {has_time}")
    
    if has_time > 0:
        sample = db.query(Activity).filter(Activity.activity_time != None, Activity.activity_time != '').limit(5).all()
        print("Sample records with time:")
        for s in sample:
            print(f"ID: {s.id[:10]}... | Date: {s.activity_date} | Time: {s.activity_time} | Name: '{s.name}'")
finally:
    db.close()
