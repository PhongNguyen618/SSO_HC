import sys
from backend.database import SessionLocal, Athlete, CompetitionRegistration, Activity

def find_duplicates():
    db = SessionLocal()
    try:
        # Lấy tất cả đăng ký của giải 2 (hoặc giải mới hơn)
        # Giả sử giải mới có ID = 2
        regs_event_2 = db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == 2).all()
        
        print(f"=== Đăng ký của giải 2: {len(regs_event_2)} ===")
        duplicates = []
        
        for reg in regs_event_2:
            athlete_2 = db.query(Athlete).filter(Athlete.id == reg.athlete_id).first()
            if not athlete_2:
                continue
                
            # Tìm xem có VĐV nào khác có cùng tên (full_name) nhưng khác strava_name
            # và đã đăng ký ở giải 1
            name_norm = athlete_2.full_name.strip().lower()
            
            other_athletes = db.query(Athlete).filter(
                Athlete.id != athlete_2.id,
                Athlete.full_name == athlete_2.full_name
            ).all()
            
            for other in other_athletes:
                # Kiểm tra xem VĐV này có đăng ký giải 1 không
                reg_1 = db.query(CompetitionRegistration).filter(
                    CompetitionRegistration.athlete_id == other.id,
                    CompetitionRegistration.event_id == 1
                ).first()
                
                if reg_1:
                    duplicates.append({
                        "new_athlete_id": athlete_2.id,
                        "new_full_name": athlete_2.full_name,
                        "new_strava_name": athlete_2.strava_name,
                        "old_athlete_id": other.id,
                        "old_full_name": other.full_name,
                        "old_strava_name": other.strava_name
                    })
                    
        print(f"Tìm thấy {len(duplicates)} trường hợp trùng Họ Tên nhưng khác Tên Strava:")
        for d in duplicates:
            print(f"- Họ Tên: {d['new_full_name']}")
            print(f"  + Giải mới (ID: {d['new_athlete_id']}): Strava = '{d['new_strava_name']}'")
            print(f"  + Giải cũ  (ID: {d['old_athlete_id']}): Strava = '{d['old_strava_name']}'")
            print()
            
    finally:
        db.close()

if __name__ == "__main__":
    find_duplicates()
