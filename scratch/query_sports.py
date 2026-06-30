import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import SessionLocal, MetsRule
db = SessionLocal()
sports = sorted(list(set(r.sport_type for r in db.query(MetsRule).all())))
print("Sports in DB:", sports)
db.close()
