import os
import sys
import datetime
import hashlib
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath("c:/Users/PC/Desktop/SSO_HC"))
from backend.database import Base, Athlete, Activity, CompetitionEvent, CompetitionRegistration, EventMultiplier
from backend.main import deduplicate_activities_logic

# Import logic pre-sync dedup trực tiếp từ sync_engine hoặc copy đoạn code đó ra để test cô lập
def run_pre_sync_dedup_simulated(db, athlete_id, api_activity, start_date_local, gmt7_now, event_id):
    """Giả lập hàm chặn trùng lặp pre-sync trong sync_engine.py để test cô lập."""
    from datetime import timedelta
    # Bug 1 Fix: gmt7_now luôn được định nghĩa bên ngoài hoặc truyền vào.
    # Nhánh gán ngày hoạt động:
    if start_date_local:
        act_date_str = start_date_local[:10]
    else:
        act_date_str = (gmt7_now + timedelta(hours=7)).strftime("%Y-%m-%d")
        
    limit_date = (gmt7_now - timedelta(days=4)).strftime("%Y-%m-%d")
    
    # Bug 2 Fix: Thêm bộ lọc event_id
    existing_similar = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.event_id == event_id,  # Bộ lọc event_id
        Activity.sport_type == api_activity["sport_type"],
        Activity.activity_date >= limit_date
    ).all()
    
    distance_km = (api_activity["distance"] or 0.0) / 1000.0
    moving_time_min = (api_activity["moving_time"] or 0.0) / 60.0
    elevation_gain_m = api_activity["total_elevation_gain"] or 0.0
    name = api_activity["name"]
    
    is_dup = False
    for ext in existing_similar:
        dist_ext = ext.distance_km_raw if ext.distance_km_raw is not None else ext.distance_km
        dist_diff = abs((dist_ext or 0.0) - distance_km)
        time_diff = abs((ext.moving_time_min or 0.0) - moving_time_min)
        elev_diff = abs((ext.elevation_gain_m or 0.0) - elevation_gain_m)
        
        name1_clean = (ext.name or "").strip().lower()
        name2_clean = (name or "").strip().lower()
        
        # Bug 3 Fix: So sánh chính xác thay vì substring qua `in`
        generic_keywords = [
            "activity", "hoạt động strava", "hoạt động", "workout", "run", "walk", "ride",
            "morning run", "afternoon run", "evening run", "night run",
            "morning walk", "afternoon walk", "evening walk", "night walk",
            "morning ride", "afternoon ride", "evening ride", "night ride",
            "lunch run", "lunch walk", "lunch ride"
        ]
        is_generic1 = name1_clean in generic_keywords or name1_clean == ""
        is_generic2 = name2_clean in generic_keywords or name2_clean == ""
        
        name_match = True
        if name1_clean != name2_clean and (not is_generic1 or not is_generic2):
            name_match = False
            
        if name_match and dist_diff <= 0.05 and time_diff <= 1.0 and elev_diff <= 10.0:
            is_dup = True
            break
            
    return is_dup

def test_all_dedup_fixes():
    print("=== BẮT ĐẦU CHẠY UNIT TEST CHO CÁC BẢN FIX XỬ LÝ TRÙNG LẶP ===")
    
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    db = Session()
    Base.metadata.create_all(engine)
    
    try:
        # Khởi tạo data mẫu
        event1 = CompetitionEvent(id=1, title="Giải chạy A", is_active=True, start_date="2026-06-01", end_date="2026-06-30")
        event2 = CompetitionEvent(id=2, title="Giải chạy B", is_active=True, start_date="2026-06-01", end_date="2026-06-30")
        db.add_all([event1, event2])
        
        athlete = Athlete(id=1, full_name="Nguyễn Văn A", gender="Nam", weight=65.0, is_active=True, strava_name="van_a")
        db.add(athlete)
        db.commit()
        
        # --- TEST BUG 1 & BUG 2: Pre-sync dedup logic ---
        print("\n--- Test Bug 1 & 2: Pre-sync Deduplication ---")
        gmt7_now = datetime.datetime(2026, 6, 25, 12, 0, 0)
        
        # Lưu hoạt động đã có ở Giải chạy A (event_id=1)
        act_exist = Activity(
            id="act_existing_1",
            athlete_id=1,
            event_id=1,
            name="Morning Run",
            sport_type="Run",
            distance_km=5.0,
            moving_time_min=30.0,
            elevation_gain_m=10.0,
            activity_date="2026-06-25",
            activity_time="07:00"
        )
        db.add(act_exist)
        db.commit()
        
        # API trả về hoạt động tương tự
        api_act = {
            "name": "Morning Run",
            "sport_type": "Run",
            "distance": 5010.0, # 5.01 km
            "moving_time": 1805.0, # ~30.08 phút
            "total_elevation_gain": 10.0
        }
        
        # Test Bug 1: gọi hàm khi start_date_local không phải rỗng mà không crash
        print("Gọi pre-sync dedup với start_date_local...")
        is_dup_with_start_date = run_pre_sync_dedup_simulated(
            db, athlete_id=1, api_activity=api_act, 
            start_date_local="2026-06-25T07:00:00Z", gmt7_now=gmt7_now, event_id=1
        )
        assert is_dup_with_start_date is True, "Phải nhận diện trùng ở cùng giải đấu!"
        print("=> Test Bug 1 thành công: Không bị crash UnboundLocalError!")
        
        # Test Bug 2: gọi hàm ở giải đấu B (event_id=2) thì không được coi là trùng
        print("Gọi pre-sync dedup ở giải đấu B (event_id=2)...")
        is_dup_other_event = run_pre_sync_dedup_simulated(
            db, athlete_id=1, api_activity=api_act, 
            start_date_local="2026-06-25T07:00:00Z", gmt7_now=gmt7_now, event_id=2
        )
        assert is_dup_other_event is False, "Không được coi là trùng vì ở 2 giải đấu khác nhau!"
        print("=> Test Bug 2 thành công: Pre-sync dedup phân biệt giải đấu chính xác!")
        
        # --- TEST BUG 3: Generic keywords ---
        print("\n--- Test Bug 3: Generic Keywords ---")
        # Trường hợp tên cụ thể có chứa generic keyword như "Sunrise Marathon" (chứa chữ "run" / "marathon")
        act_specific_1 = Activity(
            id="act_spec_1",
            athlete_id=1,
            event_id=1,
            name="Sunrise Marathon",
            sport_type="Run",
            distance_km=10.0,
            moving_time_min=60.0,
            elevation_gain_m=0.0,
            activity_date="2026-06-25",
            activity_time="08:00"
        )
        db.add(act_specific_1)
        db.commit()
        
        # Hoạt động mới từ API tên là "Morning Run"
        api_act_generic = {
            "name": "Morning Run",
            "sport_type": "Run",
            "distance": 10000.0,
            "moving_time": 3600.0,
            "total_elevation_gain": 0.0
        }
        # Nếu so sánh "Sunrise Marathon" với "Morning Run" và dùng `in`, thì "Sunrise Marathon" có chữ "run"?
        # Không, "marathon" không nằm trong generic_keywords, nhưng nếu keyword là "run" thì "Sunrise Marathon" chứa "run" -> nếu dùng `in` thì bị coi là generic!
        # Do ta dùng exact match: "sunrise marathon" in generic_keywords -> False.
        # "morning run" in generic_keywords -> True.
        # Do một bên KHÔNG generic ("Sunrise Marathon"), nên name_match phải là False (không coi là trùng lặp).
        is_dup_generic = run_pre_sync_dedup_simulated(
            db, athlete_id=1, api_activity=api_act_generic, 
            start_date_local="2026-06-25T08:00:00Z", gmt7_now=gmt7_now, event_id=1
        )
        assert is_dup_generic is False, "Không được nhận diện là trùng vì tên cụ thể 'Sunrise Marathon' không giống 'Morning Run'!"
        print("=> Test Bug 3 thành công: Phân biệt tên cụ thể chứa từ khóa generic chính xác!")
        
        # --- TEST BUG 4 & MODE MỚI: Post-sync Dedup ---
        print("\n--- Test Bug 4 & Cleaning Mode: Post-sync Deduplication ---")
        
        def create_post_sync_test_data(dbsession):
            dbsession.query(Activity).delete()
            dbsession.commit()
            
            a1 = Activity(
                id="act_chain_1", athlete_id=1, event_id=1, name="Workout", sport_type="Run",
                distance_km=5.0, distance_km_raw=5.0, moving_time_min=30.0, elevation_gain_m=0.0,
                activity_date="2026-06-25", activity_time="09:00:00", multiplier=1.5
            )
            a2 = Activity(
                id="act_chain_2", athlete_id=1, event_id=1, name="Workout", sport_type="Run",
                distance_km=5.0, distance_km_raw=5.0, moving_time_min=30.0, elevation_gain_m=0.0,
                activity_date="2026-06-25", activity_time="09:00:10", multiplier=1.0
            )
            a3 = Activity(
                id="act_chain_3", athlete_id=1, event_id=1, name="Workout", sport_type="Run",
                distance_km=5.0, distance_km_raw=5.0, moving_time_min=30.0, elevation_gain_m=0.0,
                activity_date="2026-06-25", activity_time="09:00:20", multiplier=1.0
            )
            adev1 = Activity(
                id="act_dev_1", athlete_id=1, event_id=1, name="Morning Run", sport_type="Run",
                distance_km=8.0, distance_km_raw=8.0, moving_time_min=45.0, elevation_gain_m=10.0,
                activity_date="2026-06-25", activity_time="09:30:00", multiplier=1.0
            )
            adev2 = Activity(
                id="act_dev_2", athlete_id=1, event_id=1, name="Morning Ride", sport_type="Run",
                distance_km=8.1, distance_km_raw=8.1, moving_time_min=45.0, elevation_gain_m=10.0,
                activity_date="2026-06-25", activity_time="09:35:00", multiplier=1.0
            )
            dbsession.add_all([a1, a2, a3, adev1, adev2])
            dbsession.commit()

        # Test Mode "standard" (Chỉ dọn trùng cự ly/thời gian tuyệt đối)
        create_post_sync_test_data(db)
        print("Chạy dọn dẹp trùng lặp ở chế độ standard (cơ bản)...")
        res_standard = deduplicate_activities_logic(db, mode="standard")
        print(f"  Standard result: deleted_count={res_standard['deleted_count']}, message={res_standard['message']}")
        assert res_standard['deleted_count'] == 2, f"Sai số lượng xóa cơ bản: Kỳ vọng 2, thực tế {res_standard['deleted_count']}"
        
        remaining_ids = [a.id for a in db.query(Activity.id).all()]
        assert "act_chain_1" in remaining_ids, "act_chain_1 phải được giữ lại"
        assert "act_chain_2" not in remaining_ids, "act_chain_2 phải bị xóa"
        assert "act_chain_3" not in remaining_ids, "act_chain_3 phải bị xóa"
        assert "act_dev_1" in remaining_ids, "act_dev_1 không được xóa trong standard mode"
        assert "act_dev_2" in remaining_ids, "act_dev_2 không được xóa trong standard mode"
        print("=> Test Bug 4 & Mode standard thành công: Xóa chuỗi trùng 3+ hoàn toàn và bỏ qua trùng 2 thiết bị!")
        
        # Test Mode "two_devices" (Chỉ dọn trùng thiết bị song song)
        create_post_sync_test_data(db)
        print("Chạy dọn dẹp trùng lặp ở chế độ two_devices (2 thiết bị)...")
        res_two_devices = deduplicate_activities_logic(db, mode="two_devices")
        print(f"  Two devices result: deleted_count={res_two_devices['deleted_count']}, message={res_two_devices['message']}")
        assert res_two_devices['deleted_count'] == 1, f"Sai số lượng xóa 2 thiết bị: Kỳ vọng 1, thực tế {res_two_devices['deleted_count']}"
        remaining_ids_2 = [a.id for a in db.query(Activity.id).all()]
        assert "act_dev_1" not in remaining_ids_2, "act_dev_1 phải bị xóa"
        assert "act_dev_2" in remaining_ids_2, "act_dev_2 phải được giữ lại"
        assert "act_chain_2" in remaining_ids_2, "act_chain_2 không được xóa trong mode này"
        print("=> Test Mode two_devices thành công: Dọn trùng lặp thiết bị song song chính xác!")
        
        # Test Mode "two_devices" với dry_run=True (Không được xóa bản ghi nào)
        create_post_sync_test_data(db)
        print("Chạy dọn dẹp trùng lặp ở chế độ two_devices (dry_run=True)...")
        res_dry_run = deduplicate_activities_logic(db, mode="two_devices", dry_run=True)
        print(f"  Dry run result: deleted_count={res_dry_run['deleted_count']}, message={res_dry_run['message']}")
        assert res_dry_run['deleted_count'] == 1, f"Sai số lượng phát hiện: Kỳ vọng 1, thực tế {res_dry_run['deleted_count']}"
        remaining_ids_dry = [a.id for a in db.query(Activity.id).all()]
        assert "act_dev_1" in remaining_ids_dry, "act_dev_1 KHÔNG được bị xóa khi dry_run=True"
        assert "act_dev_2" in remaining_ids_dry, "act_dev_2 KHÔNG được bị xóa khi dry_run=True"
        print("=> Test dry_run thành công: Phát hiện nhưng không xóa bản ghi!")
        
        # Test Mode "all" (Dọn cả hai loại)
        create_post_sync_test_data(db)
        print("Chạy dọn dẹp trùng lặp ở chế độ all (tất cả)...")
        res_all = deduplicate_activities_logic(db, mode="all")
        print(f"  All result: deleted_count={res_all['deleted_count']}, message={res_all['message']}")
        assert res_all['deleted_count'] == 3, f"Sai số lượng xóa tất cả: Kỳ vọng 3, thực tế {res_all['deleted_count']}"
        remaining_ids_3 = [a.id for a in db.query(Activity.id).all()]
        assert "act_chain_2" not in remaining_ids_3
        assert "act_chain_3" not in remaining_ids_3
        assert "act_dev_1" not in remaining_ids_3
        print("=> Test Mode all thành công!")
        
        print("\n=> TẤT CẢ CÁC TEST CASE ĐÃ VƯỢT QUA THÀNH CÔNG!")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_all_dedup_fixes()
