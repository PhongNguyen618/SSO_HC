import sys
import os

# Thêm thư mục gốc vào python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import SessionLocal, Athlete, CompetitionEvent, CompetitionRegistration, Activity

def check_counts():
    db = SessionLocal()
    
    # 1. Tổng số Athlete trong DB
    total_athletes = db.query(Athlete).count()
    active_athletes = db.query(Athlete).filter(Athlete.is_active == True).count()
    
    print(f"Tổng số VĐV trong database: {total_athletes}")
    print(f"Số VĐV đang Active: {active_athletes}")
    
    # 2. Danh sách các giải đấu và số lượng đăng ký của từng giải
    events = db.query(CompetitionEvent).all()
    print("\n--- Thống kê theo từng giải đấu ---")
    for ev in events:
        reg_count = db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == ev.id).count()
        # Số VĐV có hoạt động trong giải đấu này
        ath_with_activities = db.query(Activity.athlete_id).filter(Activity.event_id == ev.id, Activity.athlete_id != None).distinct().count()
        print(f"Giải đấu ID {ev.id}: {ev.title}")
        print(f"  - Số lượng đăng ký (CompetitionRegistration): {reg_count} VĐV")
        print(f"  - Số lượng VĐV có hoạt động thực tế trong giải: {ath_with_activities} VĐV")
        print(f"  - Club ID cấu hình: {ev.strava_club_id}")
        
    db.close()

if __name__ == "__main__":
    check_counts()
