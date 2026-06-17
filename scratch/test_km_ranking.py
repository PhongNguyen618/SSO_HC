import sys
import os
from sqlalchemy.orm import Session
from datetime import datetime

# Thêm thư mục gốc vào python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import SessionLocal, CompetitionEvent, Athlete, Activity, CompetitionRegistration, EventMultiplier
from backend.sync_engine import link_unlinked_activities
from backend.calculations import get_award_info

def run_test():
    print("============================================================")
    print("TEST: KM Ranking Metric & Sports Filtering & Multiplier")
    print("============================================================")
    db = SessionLocal()
    
    # 1. Tạo giải đấu giả lập
    test_event = CompetitionEvent(
        title="Giải Chạy Thử Nghiệm KM",
        strava_club_id="test_club_123",
        start_date="2026-06-01",
        end_date="2026-06-30",
        is_active=True,
        description="Giải đấu test tính theo KM và lọc bộ môn",
        ranking_metric="distance",
        ranking_sports="Run,Walk"
    )
    db.add(test_event)
    db.commit()
    db.refresh(test_event)
    event_id = test_event.id
    print(f"-> Tạo giải đấu test thành công (ID: {event_id})")

    # 2. Tạo VĐV giả lập
    test_athlete = Athlete(
        full_name="Nguyễn Văn Test",
        department="PHÒNG HÀNH CHÍNH NHÂN SỰ",
        gender="Nam",
        weight=70.0,
        strava_name="van_test_strava",
        is_active=True
    )
    db.add(test_athlete)
    db.commit()
    db.refresh(test_athlete)
    athlete_id = test_athlete.id
    print(f"-> Tạo VĐV test thành công (ID: {athlete_id})")

    # 3. Đăng ký VĐV vào giải đấu
    reg = CompetitionRegistration(athlete_id=athlete_id, event_id=event_id)
    db.add(reg)
    db.commit()

    # 4. Thêm hệ số nhân cho chủ nhật (day_of_week = 6)
    mult = EventMultiplier(
        event_id=event_id,
        day_of_week=6, # Chủ nhật
        multiplier=2.0,
        description="Chủ nhật nhân đôi"
    )
    db.add(mult)
    db.commit()
    print("-> Thêm hệ số nhân x2 cho Chủ Nhật thành công")

    # 5. Tạo các hoạt động chưa liên kết
    # Hoạt động 1: Run (Chạy bộ) vào thứ Hai (2026-06-15), 10 km
    act1 = Activity(
        id="test_act_1",
        athlete_name_raw="van_test_strava",
        name="Chạy bộ thứ hai",
        type="Run",
        sport_type="Run",
        distance_km=10.0,
        moving_time_min=60.0,
        elapsed_time_min=60.0,
        pace_min_km=6.0,
        elevation_gain_m=10.0,
        activity_date="2026-06-15", # Thứ Hai
        kcal_burned=600.0,
        event_id=event_id
    )
    # Hoạt động 2: Walk (Đi bộ) vào chủ nhật (2026-06-14), 5 km -> kì vọng nhân đôi thành 10 km
    act2 = Activity(
        id="test_act_2",
        athlete_name_raw="van_test_strava",
        name="Đi bộ chủ nhật",
        type="Walk",
        sport_type="Walk",
        distance_km=5.0,
        moving_time_min=60.0,
        elapsed_time_min=60.0,
        pace_min_km=12.0,
        elevation_gain_m=0.0,
        activity_date="2026-06-14", # Chủ Nhật
        kcal_burned=300.0,
        event_id=event_id
    )
    # Hoạt động 3: Ride (Đạp xe) vào thứ ba (2026-06-16), 20 km -> kì vọng bị loại trừ do ranking_sports="Run,Walk"
    act3 = Activity(
        id="test_act_3",
        athlete_name_raw="van_test_strava",
        name="Đạp xe thứ ba",
        type="Ride",
        sport_type="Ride",
        distance_km=20.0,
        moving_time_min=60.0,
        elapsed_time_min=60.0,
        pace_min_km=3.0,
        elevation_gain_m=20.0,
        activity_date="2026-06-16",
        kcal_burned=500.0,
        event_id=event_id
    )
    db.add_all([act1, act2, act3])
    db.commit()

    # 6. Gọi hàm liên kết hoạt động và tính toán lại
    link_unlinked_activities(db, test_athlete)
    
    # Refresh hoạt động để lấy dữ liệu mới
    db.refresh(act1)
    db.refresh(act2)
    db.refresh(act3)

    print("\n--- Kiểm tra dữ liệu hoạt động sau khi xử lý ---")
    print(f"Hoạt động 1 (Run - Thứ Hai): Distance={act1.distance_km} KM, Raw={act1.distance_km_raw} KM, Multiplier={act1.multiplier}")
    print(f"Hoạt động 2 (Walk - Chủ Nhật): Distance={act2.distance_km} KM, Raw={act2.distance_km_raw} KM, Multiplier={act2.multiplier}")
    print(f"Hoạt động 3 (Ride - Đạp xe): Distance={act3.distance_km} KM, Raw={act3.distance_km_raw} KM, Multiplier={act3.multiplier}")

    # Xác thực Hoạt động 1:
    assert act1.distance_km == 10.0, f"Error: Act1 distance should be 10.0, got {act1.distance_km}"
    assert act1.distance_km_raw == 10.0, "Error: Act1 raw distance should be 10.0"
    
    # Xác thực Hoạt động 2:
    assert act2.distance_km == 10.0, f"Error: Act2 distance should be multiplied to 10.0 (5 * 2), got {act2.distance_km}"
    assert act2.distance_km_raw == 5.0, "Error: Act2 raw distance should be 5.0"

    print("=> PASS: Hoạt động đã được nhân hệ số và lưu trữ quãng đường gốc thành công!")

    # 7. Giả lập tính toán BXH như trên trang chủ main.py
    # Lọc bộ môn cho phép
    allowed_sports = [s.strip() for s in (test_event.ranking_sports or "Run,Walk,Ride,Swim").split(",") if s.strip()]
    base_filters = [
        Activity.activity_date >= "2026-06-01",
        Activity.activity_date <= "2026-06-30",
        Activity.event_id == event_id,
        Activity.sport_type.in_(allowed_sports)
    ]

    from sqlalchemy import func
    query_stats = db.query(
        Athlete.id,
        Athlete.full_name,
        func.sum(Activity.distance_km).label("total_dist"),
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).join(Activity, Athlete.id == Activity.athlete_id)\
     .filter(Athlete.id == athlete_id, *base_filters)\
     .group_by(Athlete.id).first()

    print("\n--- Kiểm tra BXH Cá Nhân ---")
    if query_stats:
        total_dist_bxh = query_stats.total_dist
        print(f"VĐV: {query_stats.full_name}, Tổng KM trên BXH: {total_dist_bxh} KM (Kì vọng: 20.0 KM)")
        assert total_dist_bxh == 20.0, f"Error: Total distance on leaderboard should be 20.0, got {total_dist_bxh}"
        print("=> PASS: BXH đã lọc bỏ hoạt động Đạp xe (Ride) và cộng dồn quãng đường nhân hệ số của Chạy/Đi bộ!")
    else:
        print("Error: No leaderboard stats found")
        assert False

    # DỌN DẸP DỮ LIỆU TEST
    print("\n--- Dọn dẹp dữ liệu kiểm thử ---")
    db.delete(act1)
    db.delete(act2)
    db.delete(act3)
    db.delete(mult)
    db.delete(reg)
    db.delete(test_athlete)
    db.delete(test_event)
    db.commit()
    db.close()
    print("============================================================")
    print("TẤT CẢ CÁC BƯỚC KIỂM THỬ ĐỀU THÀNH CÔNG!")
    print("============================================================")

if __name__ == "__main__":
    run_test()
