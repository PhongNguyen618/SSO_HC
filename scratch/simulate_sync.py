import sqlite3
import shutil
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Copy thành DB test để chạy không ảnh hưởng tới file gốc
shutil.copy("SSO_HC_backup_v1.4.0_1783262525.db", "test_sync_minh_tu.db")

# Import các thư viện cần thiết từ backend
sys.path.append("c:/Users/PC/Desktop/SSO_HC")
from backend.database import SessionLocal, Athlete, CompetitionEvent
from backend.sync_engine import sync_single_athlete_all_events

# Override SessionLocal để dùng DB test
import sqlalchemy
from sqlalchemy.orm import sessionmaker
engine_test = sqlalchemy.create_engine("sqlite:///test_sync_minh_tu.db")
SessionTest = sessionmaker(bind=engine_test)

db = SessionTest()
athlete = db.query(Athlete).filter(Athlete.id == 102).first()

print(f"Bắt đầu chạy đồng bộ thử nghiệm cho VĐV: {athlete.full_name}")
print(f"Token ban đầu: Access={athlete.strava_access_token[:10] if athlete.strava_access_token else None}, Refresh={athlete.strava_refresh_token[:10] if athlete.strava_refresh_token else None}")

try:
    sync_single_athlete_all_events(db, athlete)
    
    # Reload lại athlete từ DB test xem token và hoạt động ra sao
    db.refresh(athlete)
    print("\n--- KẾT QUẢ SAU ĐỒNG BỘ THỬ NGHIỆM ---")
    print(f"Token hiện tại: Access={athlete.strava_access_token[:10] if athlete.strava_access_token else None}, Refresh={athlete.strava_refresh_token[:10] if athlete.strava_refresh_token else None}")
    
    # Xem các hoạt động của Tú trong DB test
    from backend.database import Activity
    acts = db.query(Activity).filter(Activity.athlete_id == 102).all()
    print(f"Số lượng hoạt động trong DB test: {len(acts)}")
    for act in acts:
        print(f"  - {act.name} | Ngày: {act.activity_date} | Quãng đường: {act.distance_km}km")
        
except Exception as e:
    print(f"Lỗi khi chạy đồng bộ: {e}")

db.close()
