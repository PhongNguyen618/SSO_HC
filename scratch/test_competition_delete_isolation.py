import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import (
    SessionLocal, Athlete, CompetitionEvent, CompetitionRegistration, 
    Activity, Config, MetsRule, RewardRule, BadgeRule, EventMultiplier
)
from backend.main import admin_delete_competition

class MockURL:
    path = "/admin/competitions/delete"

def run_test():
    db = SessionLocal()
    try:
        print("--- SETUP TEST DATA FOR COMPETITION DELETION ---")
        
        # 1. Clear any existing mock data
        test_event_title = "Mock Event Deletion Test"
        test_athlete_name = "VDV Test Comp Deletion"
        test_strava_name = "vdv_test_comp_deletion_strava"
        
        old_comp = db.query(CompetitionEvent).filter(CompetitionEvent.title == test_event_title).first()
        if old_comp:
            # Dọn dẹp thủ công phòng trường hợp khóa ngoại chưa xử lý
            db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == old_comp.id).delete()
            db.query(MetsRule).filter(MetsRule.event_id == old_comp.id).delete()
            db.query(RewardRule).filter(RewardRule.event_id == old_comp.id).delete()
            db.query(BadgeRule).filter(BadgeRule.event_id == old_comp.id).delete()
            db.query(EventMultiplier).filter(EventMultiplier.event_id == old_comp.id).delete()
            db.query(Activity).filter(Activity.event_id == old_comp.id).delete()
            db.delete(old_comp)
            db.commit()
            
        old_ath = db.query(Athlete).filter(Athlete.strava_name == test_strava_name).first()
        if old_ath:
            db.query(CompetitionRegistration).filter(CompetitionRegistration.athlete_id == old_ath.id).delete()
            db.query(Activity).filter(Activity.athlete_id == old_ath.id).delete()
            db.delete(old_ath)
            db.commit()

        # 2. Create mock event
        comp = CompetitionEvent(
            title=test_event_title,
            start_date="2026-06-01",
            end_date="2026-06-30",
            is_active=True
        )
        db.add(comp)
        db.commit()
        db.refresh(comp)
        
        # 3. Create mock athlete
        athlete = Athlete(
            full_name=test_athlete_name,
            gender="Nam",
            department="PHONG KIEM THU",
            weight=65.0,
            strava_name=test_strava_name,
            is_active=True
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        
        # 4. Register athlete to event
        reg = CompetitionRegistration(athlete_id=athlete.id, event_id=comp.id)
        db.add(reg)
        
        # 5. Create rules specific to this event
        mets_rule = MetsRule(event_id=comp.id, sport_type="Ride", min_speed=10.0, max_speed=20.0, met_value=6.0)
        reward_rule = RewardRule(event_id=comp.id, gender="Nam", kcal_threshold=500.0, reward_amount=50000.0)
        badge_rule = BadgeRule(id=f"test_badge_{comp.id}", badge_key="test_badge", event_id=comp.id, name="Test Badge", description="Test", icon="test.png", color="blue", threshold=10, unit="activities")
        multiplier = EventMultiplier(event_id=comp.id, day_of_week=6, multiplier=2.0) # Sunday
        
        db.add(mets_rule)
        db.add(reward_rule)
        db.add(badge_rule)
        db.add(multiplier)
        
        # 6. Create activity in this event
        act = Activity(
            id="mock_act_comp_delete_test",
            athlete_id=athlete.id,
            event_id=comp.id,
            athlete_name_raw=test_athlete_name,
            name="Morning Ride",
            type="Ride",
            sport_type="Ride",
            distance_km=15.0,
            moving_time_min=45.0,
            elapsed_time_min=45.0,
            activity_date="2026-06-14",
            kcal_burned=400.0,
            mets_value=6.0
        )
        db.add(act)
        
        # 7. Mock active admin session
        db.query(Config).filter(Config.key.in_(["admin_session_id", "admin_session_expiry", "admin_username"])).delete(synchronize_session=False)
        db.add(Config(key="admin_session_id", value="mock_session_id"))
        db.add(Config(key="admin_session_expiry", value=str(int(time.time() + 3600))))
        db.add(Config(key="admin_username", value="admin"))
        db.commit()

        print(f"Setup completed. Comp ID: {comp.id}, Athlete ID: {athlete.id}")

        # --- EXECUTE TEST CASE: Delete Competition ---
        print("\n--- TEST CASE: Delete competition and verify constraints ---")
        
        class RequestWithCookie:
            cookies = {"sso_hc_admin_session": "mock_session_id"}
            scope = {"type": "http"}
            url = MockURL()
            
        req = RequestWithCookie()
        
        # Call the delete endpoint
        response = admin_delete_competition(
            comp_id=comp.id,
            request=req,
            db=db
        )
        
        # Verify database state
        # 1. CompetitionEvent record MUST be deleted
        comp_db = db.query(CompetitionEvent).filter(CompetitionEvent.id == comp.id).first()
        assert comp_db is None, "CompetitionEvent must be deleted from competition_events table"
        print("Success: CompetitionEvent record is deleted.")
        
        # 2. Registration for this event MUST be deleted
        reg_db = db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == comp.id).first()
        assert reg_db is None, "Registration records for this event must be deleted"
        print("Success: Registration records are deleted.")
        
        # 3. Rules (MetsRule, RewardRule, BadgeRule, EventMultiplier) specific to this event MUST be deleted
        mets_db = db.query(MetsRule).filter(MetsRule.event_id == comp.id).all()
        assert len(mets_db) == 0, "MetsRules for this event must be deleted"
        
        rewards_db = db.query(RewardRule).filter(RewardRule.event_id == comp.id).all()
        assert len(rewards_db) == 0, "RewardRules for this event must be deleted"
        
        badges_db = db.query(BadgeRule).filter(BadgeRule.event_id == comp.id).all()
        assert len(badges_db) == 0, "BadgeRules for this event must be deleted"
        
        multipliers_db = db.query(EventMultiplier).filter(EventMultiplier.event_id == comp.id).all()
        assert len(multipliers_db) == 0, "EventMultipliers for this event must be deleted"
        print("Success: All config rules (Mets, Rewards, Badges, Multipliers) specific to this event are deleted.")
        
        # 4. Activity in this event MUST be unlinked (event_id = None) but NOT deleted
        act_db = db.query(Activity).filter(Activity.id == "mock_act_comp_delete_test").first()
        assert act_db is not None, "Activity record must still exist"
        assert act_db.event_id is None, "Activity event_id must be set to None (unlinked)"
        print("Success: Activity in this event is unlinked (event_id = None).")
        
        # 5. Athlete record MUST still exist
        ath_db = db.query(Athlete).filter(Athlete.id == athlete.id).first()
        assert ath_db is not None, "Athlete record must still exist"
        print("Success: Athlete record still exists.")

        # --- CLEANUP ---
        # Vì activity không còn event_id, ta xóa hoạt động bằng id
        db.query(Activity).filter(Activity.id == "mock_act_comp_delete_test").delete()
        db.query(Athlete).filter(Athlete.id == athlete.id).delete()
        db.commit()
        print("\nCleanup completed. COMPETITION DELETION TESTS PASSED!")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("\nAssertion or runtime error. TEST FAILED!")
        # Fallback cleanup
        try:
            db.rollback()
            # Dọn dẹp triệt để nếu lỗi
            db.query(Activity).filter(Activity.id == "mock_act_comp_delete_test").delete()
            if 'athlete' in locals():
                db.query(Athlete).filter(Athlete.id == athlete.id).delete()
            db.commit()
        except:
            pass
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
