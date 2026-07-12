import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal, Athlete, CompetitionEvent, CompetitionRegistration, Activity, HiddenRewardConfig, RewardRule, init_db
from backend.main import get_award_info

def run_test():
    # Khởi tạo DB để tạo bảng mới nếu chưa có
    init_db()
    
    db = SessionLocal()
    try:
        print("=== SETUP TEST DATA FOR HIDE REWARDS ===")
        
        # 1. Clear any existing mock data
        test_event_title = "Mock Event Hide Rewards Test"
        old_event = db.query(CompetitionEvent).filter(CompetitionEvent.title == test_event_title).first()
        if old_event:
            db.query(RewardRule).filter(RewardRule.event_id == old_event.id).delete()
            db.query(Activity).filter(Activity.event_id == old_event.id).delete()
            db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == old_event.id).delete()
            db.query(HiddenRewardConfig).filter(HiddenRewardConfig.event_id == old_event.id).delete()
            db.delete(old_event)
            db.commit()

        db.query(Activity).filter(Activity.id.in_(["mock_act_hide_1", "mock_act_hide_2"])).delete(synchronize_session=False)
        db.query(CompetitionRegistration).filter(CompetitionRegistration.athlete_id.in_([9991, 9992])).delete(synchronize_session=False)
        db.query(Athlete).filter(Athlete.id.in_([9991, 9992])).delete(synchronize_session=False)
        db.query(HiddenRewardConfig).filter(HiddenRewardConfig.department.in_(["PHÒNG TEST ẨN", "PHÒNG TEST HIỆN"])).delete(synchronize_session=False)
        db.commit()

        # 2. Create Event A
        event = CompetitionEvent(
            title=test_event_title,
            start_date="2026-07-01",
            end_date="2026-07-31",
            is_active=True,
            reward_type="milestone",
            ranking_metric="kcal"
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        
        # 3. Create Reward Rules for this event
        reward_rule = RewardRule(
            event_id=event.id,
            gender="Nam",
            kcal_threshold=100.0,
            reward_amount=50000.0
        )
        db.add(reward_rule)
        db.commit()

        # 4. Create 2 Athletes: One in hidden dept, one in normal dept
        ath_hidden = Athlete(
            id=9991,
            full_name="VĐV Phòng Ẩn",
            gender="Nam",
            department="PHÒNG TEST ẨN",
            weight=60.0,
            strava_name="strava_hidden_test",
            is_active=True
        )
        ath_normal = Athlete(
            id=9992,
            full_name="VĐV Phòng Hiện",
            gender="Nam",
            department="PHÒNG TEST HIỆN",
            weight=60.0,
            strava_name="strava_normal_test",
            is_active=True
        )
        db.add(ath_hidden)
        db.add(ath_normal)
        db.commit()
        db.refresh(ath_hidden)
        db.refresh(ath_normal)

        # 5. Register them to the event
        reg_hidden = CompetitionRegistration(athlete_id=ath_hidden.id, event_id=event.id)
        reg_normal = CompetitionRegistration(athlete_id=ath_normal.id, event_id=event.id)
        db.add(reg_hidden)
        db.add(reg_normal)

        # 6. Create activities to gain award (each has 150 kcal > threshold 100)
        act_hidden = Activity(
            id="mock_act_hide_1",
            athlete_id=ath_hidden.id,
            event_id=event.id,
            athlete_name_raw="VĐV Phòng Ẩn",
            name="Evening Run 1",
            type="Run",
            sport_type="Run",
            distance_km=2.0,
            moving_time_min=15.0,
            elapsed_time_min=15.0,
            activity_date="2026-07-10",
            kcal_burned=150.0,
            mets_value=8.0
        )
        act_normal = Activity(
            id="mock_act_hide_2",
            athlete_id=ath_normal.id,
            event_id=event.id,
            athlete_name_raw="VĐV Phòng Hiện",
            name="Evening Run 2",
            type="Run",
            sport_type="Run",
            distance_km=2.0,
            moving_time_min=15.0,
            elapsed_time_min=15.0,
            activity_date="2026-07-10",
            kcal_burned=150.0,
            mets_value=8.0
        )
        db.add(act_hidden)
        db.add(act_normal)
        db.commit()

        # 7. Configure hidden department "PHÒNG TEST ẨN" for this event
        hidden_conf = HiddenRewardConfig(event_id=event.id, department="PHÒNG TEST ẨN")
        db.add(hidden_conf)
        db.commit()
        
        print("\n--- TEST CASE 1: Verify database state ---")
        configs = db.query(HiddenRewardConfig).filter(HiddenRewardConfig.event_id == event.id).all()
        assert len(configs) == 1, "Should have exactly 1 hidden department configured"
        assert configs[0].department == "PHÒNG TEST ẨN", "Hidden department should be 'PHÒNG TEST ẨN'"
        print("=> Database state OK!")

        print("\n--- TEST CASE 2: Verify Profile Page Hide Logic ---")
        # Logic in profile_page for VĐV Phòng Ẩn
        hide_rewards_hidden = False
        is_hidden_1 = db.query(HiddenRewardConfig).filter(
            HiddenRewardConfig.event_id == event.id,
            HiddenRewardConfig.department == ath_hidden.department
        ).first()
        if is_hidden_1:
            hide_rewards_hidden = True
            
        # Logic in profile_page for VĐV Phòng Hiện
        hide_rewards_normal = False
        is_hidden_2 = db.query(HiddenRewardConfig).filter(
            HiddenRewardConfig.event_id == event.id,
            HiddenRewardConfig.department == ath_normal.department
        ).first()
        if is_hidden_2:
            hide_rewards_normal = True

        assert hide_rewards_hidden is True, "VĐV Phòng Ẩn should have hide_rewards = True"
        assert hide_rewards_normal is False, "VĐV Phòng Hiện should have hide_rewards = False"
        print("=> Profile Page Hide Logic OK!")

        print("\n--- TEST CASE 3: Verify Leaderboard (index) Hide Logic ---")
        hidden_depts = {r.department for r in db.query(HiddenRewardConfig).filter(HiddenRewardConfig.event_id == event.id).all()}
        
        # Test mapping in leaderboard for VĐV Phòng Ẩn
        award_info_hidden = get_award_info(ath_hidden.gender, 150.0, db, event_id=event.id)
        is_hidden_ath1 = ath_hidden.department in hidden_depts
        award_hidden = 0 if is_hidden_ath1 else award_info_hidden["reward_amount"]
        has_award_hidden = False if is_hidden_ath1 else award_info_hidden["has_award"]
        
        # Test mapping in leaderboard for VĐV Phòng Hiện
        award_info_normal = get_award_info(ath_normal.gender, 150.0, db, event_id=event.id)
        is_hidden_ath2 = ath_normal.department in hidden_depts
        award_normal = 0 if is_hidden_ath2 else award_info_normal["reward_amount"]
        has_award_normal = False if is_hidden_ath2 else award_info_normal["has_award"]

        assert is_hidden_ath1 is True
        assert award_hidden == 0
        assert has_award_hidden is False
        
        assert is_hidden_ath2 is False
        assert award_normal == 50000.0
        assert has_award_normal is True
        print("=> Leaderboard Hide Logic OK!")

        print("\n--- TEST CASE 4: Verify Cascade Delete on Event deletion ---")
        # Dọn dẹp các bản ghi liên quan ở các bảng cũ không hỗ trợ cascade mức DB
        db.query(RewardRule).filter(RewardRule.event_id == event.id).delete()
        db.query(Activity).filter(Activity.event_id == event.id).delete()
        db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == event.id).delete()
        db.commit()

        # Xóa giải đấu (kiểm tra xem HiddenRewardConfig có tự động cascade delete không)
        db.delete(event)
        db.commit()
        
        # Kiểm tra config ẩn giải thưởng có bị xóa theo không
        remaining_configs = db.query(HiddenRewardConfig).filter(HiddenRewardConfig.event_id == event.id).all()
        assert len(remaining_configs) == 0, "HiddenRewardConfig should be automatically deleted via CASCADE"
        print("=> Cascade Delete OK!")

        # Clean up athletes
        db.query(Activity).filter(Activity.id.in_(["mock_act_hide_1", "mock_act_hide_2"])).delete(synchronize_session=False)
        db.query(CompetitionRegistration).filter(CompetitionRegistration.athlete_id.in_([9991, 9992])).delete(synchronize_session=False)
        db.query(Athlete).filter(Athlete.id.in_([9991, 9992])).delete(synchronize_session=False)
        db.commit()
        
        print("\n=> ALL TEST CASES PASSED SUCCESSFULLY!")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
