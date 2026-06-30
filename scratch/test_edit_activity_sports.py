import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal, Athlete, CompetitionEvent, Activity, Config, MetsRule
from backend.main import edit_activity

class MockURL:
    path = "/admin/activity/edit"

def run_test():
    db = SessionLocal()
    try:
        print("--- SETUP TEST DATA FOR EDIT ACTIVITY SPORTS ---")
        
        # 1. Dọn dẹp dữ liệu cũ nếu có
        test_athlete_name = "VDV Test Edit Sport"
        test_strava_name = "vdv_test_edit_sport_strava"
        test_act_id = "mock_act_edit_sport_test"
        
        old_ath = db.query(Athlete).filter(Athlete.strava_name == test_strava_name).first()
        if old_ath:
            db.query(Activity).filter(Activity.athlete_id == old_ath.id).delete()
            db.delete(old_ath)
            db.commit()
            
        db.query(Activity).filter(Activity.id == test_act_id).delete()
        db.commit()

        # 2. Tạo VĐV Mock (cân nặng 60kg để dễ tính)
        athlete = Athlete(
            full_name=test_athlete_name,
            gender="Nữ",
            department="PHONG KIEM THU",
            weight=60.0,
            strava_name=test_strava_name,
            is_active=True
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        
        # 3. Đảm bảo có MetsRule cho Badminton trong DB
        # Thường Badminton có METs cố định trong DB (không phụ thuộc tốc độ), hoặc khoảng tốc độ.
        # Hãy kiểm tra xem trong DB đã có Badminton chưa. Nếu chưa thì thêm vào.
        badminton_rule = db.query(MetsRule).filter(MetsRule.sport_type.ilike("Badminton")).first()
        if not badminton_rule:
            badminton_rule = MetsRule(sport_type="Badminton", min_speed=0.0, max_speed=999.0, met_value=4.5)
            db.add(badminton_rule)
            db.commit()
            
        print(f"Badminton METs in DB: {badminton_rule.met_value}")

        # 4. Tạo hoạt động Mock ban đầu (Run)
        act = Activity(
            id=test_act_id,
            athlete_id=athlete.id,
            athlete_name_raw=test_athlete_name,
            name="Afternoon Run",
            type="Run",
            sport_type="Run",
            distance_km=5.0,
            moving_time_min=30.0,
            elapsed_time_min=30.0,
            activity_date="2026-06-20",
            kcal_burned=300.0,
            mets_value=8.0
        )
        db.add(act)
        
        # 5. Mock active admin session
        db.query(Config).filter(Config.key.in_(["admin_session_id", "admin_session_expiry", "admin_username"])).delete(synchronize_session=False)
        db.add(Config(key="admin_session_id", value="mock_session_id"))
        db.add(Config(key="admin_session_expiry", value=str(int(time.time() + 3600))))
        db.add(Config(key="admin_username", value="admin"))
        db.commit()
        
        print("Setup completed.")

        # --- EXECUTE TEST CASE: Edit Activity to Badminton ---
        print("\n--- TEST CASE: Edit activity sport_type to Badminton ---")
        
        class RequestWithCookie:
            cookies = {"sso_hc_admin_session": "mock_session_id"}
            scope = {"type": "http"}
            url = MockURL()
            
        req = RequestWithCookie()
        
        # Gọi edit_activity API
        # Ta sửa sport_type sang Badminton. Khoảng cách 0 km (môn phụ trợ), thời gian 60 phút.
        # Với cân nặng 60kg, METs = 4.5, thời gian = 60 phút (1 giờ):
        # KCAL = METs * weight * duration = 4.5 * 60 * 1.0 = 270 KCAL.
        response = edit_activity(
            activity_id=test_act_id,
            request=req,
            name="Chơi Cầu Lông Chiều",
            sport_type="Badminton",
            distance_km=0.0,
            moving_time_min=60.0,
            elapsed_time_min=60.0,
            elevation_gain_m=0.0,
            activity_date="2026-06-20",
            activity_time="17:00",
            kcal_burned=None, # Tự động tính lại
            db=db
        )
        
        # Xác minh
        act_db = db.query(Activity).filter(Activity.id == test_act_id).first()
        print(f"Updated Act: sport_type={act_db.sport_type}, mets_value={act_db.mets_value}, kcal_burned={act_db.kcal_burned}")
        
        assert act_db.sport_type == "Badminton"
        assert act_db.mets_value == badminton_rule.met_value
        expected_kcal = round(badminton_rule.met_value * athlete.weight * (60.0 / 60.0))
        assert int(act_db.kcal_burned) == expected_kcal
        print("Success: Activity sport_type edited, METs and KCAL calculated correctly.")

        # --- CLEANUP ---
        db.query(Activity).filter(Activity.id == test_act_id).delete()
        db.query(Athlete).filter(Athlete.id == athlete.id).delete()
        db.commit()
        print("\nCleanup completed. TEST PASSED!")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("\nAssertion or runtime error. TEST FAILED!")
        try:
            db.rollback()
            db.query(Activity).filter(Activity.id == test_act_id).delete()
            if 'athlete' in locals():
                db.query(Athlete).filter(Athlete.id == athlete.id).delete()
            db.commit()
        except:
            pass
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
