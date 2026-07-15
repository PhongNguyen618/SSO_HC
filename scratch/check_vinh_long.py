"""Print all unique departments in the database to find Vĩnh Long or similar."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Athlete
db = SessionLocal()

try:
    athletes = db.query(Athlete).all()
    depts = set(a.department for a in athletes if a.department)
    print("All unique departments in DB:")
    for d in sorted(depts):
        count = db.query(Athlete).filter(Athlete.department == d).count()
        print(f"- '{d}' (length: {len(d)}, count: {count}) -> Hex: {d.encode('utf-8').hex()}")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    db.close()
