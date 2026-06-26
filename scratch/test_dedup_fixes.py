import os
import sys
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.database import Base, Athlete, Activity, CompetitionEvent, CompetitionRegistration
from backend.main import deduplicate_activities_logic

def run_tests():
    print("==================================================")
    print("RUNNING AUTOMATED TESTS FOR DEDUPLICATION BUG FIXES")
    print("==================================================")
    
    # Khởi tạo DB test in-memory
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    db = Session()
    Base.metadata.create_all(engine)
    
    try:
        # Thiết lập dữ liệu mẫu
        # Tạo 2 giải đấu (event_id 1 và 2) có strava_club_id
        event1 = CompetitionEvent(id=1, title="Event 1", is_active=True, start_date="2026-06-01", end_date="2026-06-30", strava_club_id="123")
        event2 = CompetitionEvent(id=2, title="Event 2", is_active=True, start_date="2026-06-01", end_date="2026-06-30", strava_club_id="456")
        db.add_all([event1, event2])
        
        # Tạo 1 VĐV
        athlete = Athlete(id=1, full_name="Lê Văn Thái", gender="Nam", weight=60.0, is_active=True, strava_name="lê văn thái")
        db.add(athlete)
        
        # Đăng ký cả 2 giải đấu
        db.add_all([
            CompetitionRegistration(event_id=1, athlete_id=1),
            CompetitionRegistration(event_id=2, athlete_id=1)
        ])
        db.commit()
        
        # --------------------------------------------------
        # TEST BUG #1 & BUG #2: sync_engine.py
        # Chúng ta import hàm _sync_single_event từ sync_engine.py để test
        # --------------------------------------------------
        print("\n--- Testing BUG #1 (gmt7_now scope) & BUG #2 (event_id isolation) in sync_engine.py ---")
        from backend.sync_engine import _sync_single_event
        
        # Mocking Strava activities
        # act_has_date có start_date_local (nhánh if)
        # act_no_date không có start_date_local (nhánh else) - Đặt thông số khác đi để không bị pre-sync chặn
        mock_activities = [
            {
                "name": "Morning Run",
                "type": "Run",
                "sport_type": "Run",
                "distance": 5000.0,
                "moving_time": 1800.0,
                "elapsed_time": 1800.0,
                "total_elevation_gain": 10.0,
                "start_date_local": "2026-06-25T07:00:00Z", # Có start_date_local
                "athlete": {"firstname": "Lê", "lastname": "Văn Thái"}
            },
            {
                "name": "Evening Run",
                "type": "Run",
                "sport_type": "Run",
                "distance": 8000.0, # 8.0 km (khác cự ly)
                "moving_time": 2880.0, # 48.0 min (khác thời gian)
                "elapsed_time": 2880.0,
                "total_elevation_gain": 15.0,
                "start_date_local": None, # Không có start_date_local (sẽ đi vào else, gán gmt7_now)
                "athlete": {"firstname": "Lê", "lastname": "Văn Thái"}
            }
        ]
        
        # Chạy đồng bộ cho Event 1
        # Mock configs và token
        configs = {"sync_grace_period_hours": "12"}
        token = "mock_token"
        
        # Thay thế hàm requests.get để mock kết quả API
        import requests
        original_get = requests.get
        
        class MockResponse:
            def __init__(self, json_data):
                self.json_data = json_data
            def raise_for_status(self):
                pass
            def json(self):
                return self.json_data
                
        # Mock trả về chunk hoạt động rồi trả về rỗng ở page tiếp theo
        def mock_get(url, *args, **kwargs):
            params = kwargs.get("params", {})
            page = params.get("page", 1)
            if page == 1:
                return MockResponse(mock_activities)
            return MockResponse([])
            
        requests.get = mock_get
        
        try:
            # 1. Chạy sync cho Event 1
            res1 = _sync_single_event(db, configs, token, event1)
            print(f"Sync Event 1 status: {res1.get('status')}, error: {res1.get('error')}, new activities: {res1.get('new_activities')}")
            # Đảm bảo không bị UnboundLocalError (BUG #1) và thêm hoạt động thành công
            activities_ev1 = db.query(Activity).filter(Activity.event_id == 1).all()
            print(f"Activities in Event 1: {len(activities_ev1)}")
            assert len(activities_ev1) == 2, f"Failed: Expected 2 activities, got {len(activities_ev1)}"
            print("  BUG #1 Test: PASSED (No UnboundLocalError when start_date_local exists/missing)")
            
            # 2. Chạy sync cho Event 2 với các hoạt động tương tự
            # Vì ta đã fix BUG #2 (thêm event_id vào pre-sync filter), các hoạt động này KHÔNG được phép
            # bị chặn là trùng lặp bởi các hoạt động của Event 1.
            res2 = _sync_single_event(db, configs, token, event2)
            print(f"Sync Event 2 status: {res2.get('status')}, error: {res2.get('error')}, new activities: {res2.get('new_activities')}")
            activities_ev2 = db.query(Activity).filter(Activity.event_id == 2).all()
            print(f"Activities in Event 2: {len(activities_ev2)}")
            assert len(activities_ev2) == 2, f"Failed: BUG #2 event_id isolation not working. Expected 2, got {len(activities_ev2)}"
            print("  BUG #2 Test: PASSED (Event isolation works, no false cross-event deduplication)")
            
        finally:
            requests.get = original_get
            
        # --------------------------------------------------
        # TEST BUG #3: Generic keywords matching
        # --------------------------------------------------
        print("\n--- Testing BUG #3 (Generic keywords false positive) ---")
        # Xóa tất cả các hoạt động cũ để test sạch
        db.query(Activity).delete()
        db.commit()
        
        # Giả lập: 2 hoạt động có cự ly và thời gian tương tự, cùng ngày
        # Một cái có tên "Sunrise Marathon Training", một cái "Evening Run" (hoặc "Afternoon Run")
        # Vì "Sunrise Marathon Training" KHÔNG phải generic keyword, chúng không được gộp trùng lặp.
        act_marathon = Activity(
            id="act_marathon",
            athlete_id=1,
            event_id=1,
            athlete_name_raw="lê văn thái",
            name="Sunrise Marathon Training",
            type="Run",
            sport_type="Run",
            distance_km=10.0,
            distance_km_raw=10.0,
            moving_time_min=60.0,
            activity_date="2026-06-25",
            multiplier=1.0
        )
        act_run = Activity(
            id="act_run",
            athlete_id=1,
            event_id=1,
            athlete_name_raw="lê văn thái",
            name="Afternoon Run",
            type="Run",
            sport_type="Run",
            distance_km=10.05,
            distance_km_raw=10.05,
            moving_time_min=60.5,
            activity_date="2026-06-25",
            multiplier=1.0
        )
        db.add_all([act_marathon, act_run])
        db.commit()
        
        # Chạy post-sync dedup
        res_dedup = deduplicate_activities_logic(db)
        print(f"Deduplicate result: deleted {res_dedup.get('deleted_count')} activities.")
        
        # Đảm bảo không bị xóa hoạt động marathon (không bị false positive)
        remaining = db.query(Activity).all()
        print(f"Remaining activities (expecting 2): {len(remaining)}")
        assert len(remaining) == 2, f"Failed: BUG #3 false positive, Marathon activity was deleted!"
        print("  BUG #3 Test: PASSED (Non-generic naming differences are respected)")
        
        # --------------------------------------------------
        # TEST BUG #4: Post-sync Dedup break logic
        # --------------------------------------------------
        print("\n--- Testing BUG #4 (Post-sync Dedup multi-duplicate groups) ---")
        db.query(Activity).delete()
        db.commit()
        
        # Test 3 hoạt động trùng nhau hoàn toàn:
        # A (mult 1.0), B (mult 3.0), C (mult 2.0). Trùng nhau hoàn toàn.
        # Đảm bảo sau khi chạy deduplicate_activities_logic, chỉ còn lại B.
        print("\n--- Test 3 activities duplicated completely: A(1.0), B(3.0), C(2.0) ---")
        act_A = Activity(
            id="act_A", athlete_id=1, event_id=1, athlete_name_raw="lê văn thái",
            name="Morning Run", type="Run", sport_type="Run",
            distance_km=5.0, distance_km_raw=5.0, moving_time_min=30.0,
            activity_date="2026-06-25", multiplier=1.0
        )
        act_B = Activity(
            id="act_B", athlete_id=1, event_id=1, athlete_name_raw="lê văn thái",
            name="Morning Run", type="Run", sport_type="Run",
            distance_km=5.0, distance_km_raw=5.0, moving_time_min=30.0,
            activity_date="2026-06-25", multiplier=3.0
        )
        act_C = Activity(
            id="act_C", athlete_id=1, event_id=1, athlete_name_raw="lê văn thái",
            name="Morning Run", type="Run", sport_type="Run",
            distance_km=5.0, distance_km_raw=5.0, moving_time_min=30.0,
            activity_date="2026-06-25", multiplier=2.0
        )
        db.add_all([act_A, act_B, act_C])
        db.commit()
        
        res = deduplicate_activities_logic(db)
        print(f"Deleted count: {res.get('deleted_count')}")
        remaining = db.query(Activity).all()
        print(f"Remaining: {[r.id for r in remaining]}")
        assert len(remaining) == 1, f"Failed: Expected 1 activity remaining, got {len(remaining)}"
        assert remaining[0].id == "act_B", f"Failed: Expected act_B to be kept, got {remaining[0].id}"
        print("  BUG #4 Test: PASSED (Multi-duplicate group resolved correctly, keeping highest multiplier)")
        
        # --------------------------------------------------
        # TEST NEW FEATURE: Time Overlap Deduplication (Trường hợp Lê Văn Thái)
        # --------------------------------------------------
        print("\n--- Testing Time Overlap Deduplication (Le Van Thai Case) ---")
        db.query(Activity).delete()
        db.commit()
        
        # Tạo 2 hoạt động ghi song song:
        # Act 1: Huawei Watch - 7.89 km, 56m 14s (56.23 min), start 05:13
        # Act 2: Strava App - 8.38 km, 57m 24s (57.4 min), start 05:13 (hoặc 05:14)
        # Cả hai có multiplier giống nhau (1.0). Thuật toán phải gộp chúng lại và giữ lại Act 2 (8.38 km vì dài hơn).
        act_huawei = Activity(
            id="act_huawei",
            athlete_id=1,
            event_id=1,
            athlete_name_raw="lê văn thái",
            name="Chạy ngoài trời",
            type="Run",
            sport_type="Run",
            distance_km=7.89,
            distance_km_raw=7.89,
            moving_time_min=56.23,
            elapsed_time_min=56.23,
            activity_date="2026-06-26",
            activity_time="05:13",
            multiplier=1.0
        )
        act_strava_app = Activity(
            id="act_strava_app",
            athlete_id=1,
            event_id=1,
            athlete_name_raw="lê văn thái",
            name="Chạy bộ buổi sáng",
            type="Run",
            sport_type="Run",
            distance_km=8.38,
            distance_km_raw=8.38,
            moving_time_min=57.4,
            elapsed_time_min=57.4,
            activity_date="2026-06-26",
            activity_time="05:13",
            multiplier=1.0
        )
        db.add_all([act_huawei, act_strava_app])
        db.commit()
        
        # Chạy logic dọn trùng
        res_overlap = deduplicate_activities_logic(db)
        print(f"Deleted count for overlap test: {res_overlap.get('deleted_count')}")
        
        remaining_overlap = db.query(Activity).all()
        print(f"Remaining activities count: {len(remaining_overlap)}")
        for r in remaining_overlap:
            # Dùng encode sang ascii trực tiếp để thay thế toàn bộ ký tự Unicode bằng dấu ?
            name_ascii = r.name.encode('ascii', errors='replace').decode('ascii')
            print(f"  Kept ID: {r.id} | Name: '{name_ascii}' | Dist: {r.distance_km} km")
            
        assert len(remaining_overlap) == 1, f"Failed: Expected 1 activity, got {len(remaining_overlap)} (Time Overlap did not group them)"
        assert remaining_overlap[0].id == "act_strava_app", f"Failed: Expected act_strava_app (8.38 km) to be kept, got {remaining_overlap[0].id}"
        print("  Time Overlap Deduplication Test: PASSED (Successfully grouped parallel records and kept longest distance)")
        
        # --------------------------------------------------
        # TEST SAFETY: 2 hoạt động thật sự khác nhau trong ngày (ví dụ 5km và 8km)
        # Kể cả khi chúng cùng nhận giờ sync (activity_time = "05:13")
        # Hệ thống phải giữ lại CẢ HAI hoạt động (không được gộp nhầm/xóa ngầm).
        # --------------------------------------------------
        print("\n--- Testing Safety: Real different activities are NOT merged ---")
        db.query(Activity).delete()
        db.commit()
        
        act_run_morning = Activity(
            id="act_run_morning",
            athlete_id=1,
            event_id=1,
            athlete_name_raw="lê văn thái",
            name="Morning Run 5K",
            type="Run",
            sport_type="Run",
            distance_km=5.0,
            distance_km_raw=5.0,
            moving_time_min=30.0,
            elapsed_time_min=30.0,
            activity_date="2026-06-26",
            activity_time="05:13",
            multiplier=1.0
        )
        act_run_evening = Activity(
            id="act_run_evening",
            athlete_id=1,
            event_id=1,
            athlete_name_raw="lê văn thái",
            name="Evening Run 8K",
            type="Run",
            sport_type="Run",
            distance_km=8.0,
            distance_km_raw=8.0,
            moving_time_min=48.0,
            elapsed_time_min=48.0,
            activity_date="2026-06-26",
            activity_time="05:13", # Giả sử cùng giờ sync
            multiplier=1.0
        )
        db.add_all([act_run_morning, act_run_evening])
        db.commit()
        
        res_safety = deduplicate_activities_logic(db)
        print(f"Deleted count for safety test: {res_safety.get('deleted_count')}")
        remaining_safety = db.query(Activity).all()
        print(f"Remaining activities count (expecting 2): {len(remaining_safety)}")
        assert len(remaining_safety) == 2, f"Failed: Safety test failed. One of the real activities was deleted!"
        print("  Safety Test: PASSED (Real activities with different distances are safely preserved)")
        
        print("\n==================================================")
        print("ALL TESTS PASSED SUCCESSFULLY!")
        print("==================================================")
        
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
