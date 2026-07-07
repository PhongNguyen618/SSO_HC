import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.append("c:/Users/PC/Desktop/SSO_HC")
from backend.database import SessionLocal, Athlete, CompetitionEvent
from backend.sync_engine import refresh_user_strava_token, sync_athlete_activities_api

db_path = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("""
    SELECT id, full_name, strava_access_token, strava_refresh_token, strava_expires_at
    FROM athletes 
    WHERE id = 102
""")
athlete_row = cur.fetchone()
conn.close()

# Sử dụng Session giả lập DB test để không ảnh hưởng DB chính
import sqlalchemy
from sqlalchemy.orm import sessionmaker
engine_test = sqlalchemy.create_engine("sqlite:///test_sync_minh_tu.db")
SessionTest = sessionmaker(bind=engine_test)
db = SessionTest()

# Khởi tạo đối tượng athlete trong session
athlete = db.query(Athlete).filter(Athlete.id == 102).first()
configs = {"strava_client_id": "YOUR_CLIENT_ID", "strava_client_secret": "YOUR_SECRET"} 

event = db.query(CompetitionEvent).filter(CompetitionEvent.id == 2).first()
print(f"Giải đấu đang xét: {event.title} (ID={event.id})")
print(f"Khoảng thời gian: {event.start_date} -> {event.end_date}")

# Lấy các hoạt động
ath_acts = sync_athlete_activities_api(db, athlete, athlete.strava_access_token, event.start_date)
print(f"Tổng số hoạt động lấy từ API: {len(ath_acts)}")

for i, act in enumerate(ath_acts):
    start_date_local = act.get("start_date_local")
    act_date_str = start_date_local[:10] if start_date_local else None
    
    # Giả lập logic kiểm tra ngày
    is_valid_date = True
    if event.start_date and act_date_str < event.start_date:
        is_valid_date = False
    if event.end_date and act_date_str > event.end_date:
        is_valid_date = False
        
    original_id = act.get("id")
    act_id = f"{original_id}_{event.id}"
    
    # Kiểm tra xem hoạt động đã tồn tại chưa
    from backend.database import Activity
    exists = db.query(Activity).filter(Activity.id == act_id).first()
    
    print(f"Act {i+1}: ID={act_id} | Tên={act.get('name')} | Ngày={act_date_str} | Hợp lệ ngày={is_valid_date} | Đã có trong DB={bool(exists)}")

db.close()
