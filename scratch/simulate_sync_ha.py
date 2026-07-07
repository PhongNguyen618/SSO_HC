import sqlite3
import shutil
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Copy bản backup lúc Hà vẫn còn liên kết (ví dụ bản 1783262525) để chạy thử
shutil.copy("SSO_HC_backup_v1.4.0_1783262525.db", "test_sync_ha.db")

sys.path.append("c:/Users/PC/Desktop/SSO_HC")
from backend.database import SessionLocal, Athlete, CompetitionEvent
from backend.sync_engine import sync_single_athlete_all_events

# Override SessionLocal để dùng DB test
import sqlalchemy
from sqlalchemy.orm import sessionmaker
engine_test = sqlalchemy.create_engine("sqlite:///test_sync_ha.db")
SessionTest = sessionmaker(bind=engine_test)

db = SessionTest()
athlete = db.query(Athlete).filter(Athlete.id == 51).first()

print(f"Bắt đầu chạy đồng bộ thử cho VĐV: {athlete.full_name}")
print(f"Token ban đầu: Access={athlete.strava_access_token[:10]}, Refresh={athlete.strava_refresh_token[:10]}")

# Kiểm tra số hoạt động cào web cũ (SHA-256) trước khi đồng bộ
from backend.database import Activity
cur = db.query(Activity).filter(Activity.athlete_id == 51)
print(f"Số hoạt động TRƯỚC đồng bộ: {cur.count()}")
old_acts = cur.all()
for a in old_acts[:3]:
    print(f"  - Old Act: ID={a.id[:10]}... | Ngày={a.activity_date} | Quãng đường={a.distance_km}km")

try:
    # Chạy đồng bộ
    sync_single_athlete_all_events(db, athlete)
    
    # Reload lại athlete và kiểm tra số hoạt động
    db.refresh(athlete)
    print("\n--- KẾT QUẢ SAU ĐỒNG BỘ ---")
    print(f"Token hiện tại: Access={athlete.strava_access_token[:10] if athlete.strava_access_token else None}")
    
    cur_new = db.query(Activity).filter(Activity.athlete_id == 51)
    print(f"Số hoạt động SAU đồng bộ: {cur_new.count()}")
    new_acts = cur_new.all()
    for a in new_acts[:5]:
        print(f"  - New Act: ID={a.id} | Ngày={a.activity_date} | Quãng đường={a.distance_km}km")
        
except Exception as e:
    print(f"Lỗi khi đồng bộ: {e}")

db.close()
