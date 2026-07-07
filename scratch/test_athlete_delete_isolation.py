import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal, Athlete, CompetitionEvent, CompetitionRegistration, Activity, Config
from backend.main import admin_delete_athlete

class MockURL:
    path = "/admin/athlete/delete"

def run_test():
    db = SessionLocal()
    try:
        print("--- SETUP TEST DATA ---")
        # 1. Clear any existing mock data
        test_strava_name = "athlete_test_deletion_isolation_strava"
        old_ath = db.query(Athlete).filter(Athlete.strava_name == test_strava_name).first()
        if old_ath:
            db.query(CompetitionRegistration).filter(CompetitionRegistration.athlete_id == old_ath.id).delete()
            db.query(Activity).filter(Activity.athlete_id == old_ath.id).delete()
            db.delete(old_ath)
            db.commit()

        event_a_title = "Mock Event A Deletion Isolation"
        event_b_title = "Mock Event B Deletion Isolation"
        
        db.query(Activity).filter(Activity.id.in_(["mock_act_a_test", "mock_act_b_test"])).delete(synchronize_session=False)
        db.query(CompetitionEvent).filter(CompetitionEvent.title.in_([event_a_title, event_b_title])).delete(synchronize_session=False)
        db.commit()

        # 2. Create Event A & Event B
        event_a = CompetitionEvent(title=event_a_title, start_date="2026-06-01", end_date="2026-06-30", is_active=True)
        event_b = CompetitionEvent(title=event_b_title, start_date="2026-06-01", end_date="2026-06-30", is_active=True)
        db.add(event_a)
        db.add(event_b)
        db.commit()
        db.refresh(event_a)
        db.refresh(event_b)
        
        # 3. Create Athlete
        athlete = Athlete(
            full_name="VDV Test Isolation",
            gender="Nam",
            department="PHONG TEST",
            weight=70.0,
            strava_name=test_strava_name,
            is_active=True
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        
        # 4. Register athlete to Event A & Event B
        reg_a = CompetitionRegistration(athlete_id=athlete.id, event_id=event_a.id)
        reg_b = CompetitionRegistration(athlete_id=athlete.id, event_id=event_b.id)
        db.add(reg_a)
        db.add(reg_b)
        
        # 5. Create some mock activities for both events
        act_a = Activity(
            id="mock_act_a_test",
            athlete_id=athlete.id,
            event_id=event_a.id,
            athlete_name_raw="VDV Test Isolation",
            name="Afternoon Run A",
            type="Run",
            sport_type="Run",
            distance_km=5.0,
            moving_time_min=30.0,
            elapsed_time_min=30.0,
            activity_date="2026-06-15",
            kcal_burned=300.0,
            mets_value=8.0
        )
        act_b = Activity(
            id="mock_act_b_test",
            athlete_id=athlete.id,
            event_id=event_b.id,
            athlete_name_raw="VDV Test Isolation",
            name="Afternoon Run B",
            type="Run",
            sport_type="Run",
            distance_km=10.0,
            moving_time_min=60.0,
            elapsed_time_min=60.0,
            activity_date="2026-06-16",
            kcal_burned=600.0,
            mets_value=8.0
        )
        db.add(act_a)
        db.add(act_b)
        
        # 6. Mock active admin session in Config table
        db.query(Config).filter(Config.key.in_(["admin_session_id", "admin_session_expiry", "admin_username"])).delete(synchronize_session=False)
        db.add(Config(key="admin_session_id", value="mock_session_id"))
        db.add(Config(key="admin_session_expiry", value=str(int(time.time() + 3600))))
        db.add(Config(key="admin_username", value="admin"))
        db.commit()

        print(f"Setup completed. Athlete ID: {athlete.id}, Event A ID: {event_a.id}, Event B ID: {event_b.id}")

        # --- EXECUTE TEST CASE 1: Delete from Event A ---
        print("\n--- TEST CASE 1: Delete athlete from Event A only ---")
        
        class RequestWithCookie:
            cookies = {"sso_hc_admin_session": "mock_session_id"}
            scope = {"type": "http"}
            url = MockURL()
            
        req = RequestWithCookie()
        
        # Call the delete endpoint for event_a
        response = admin_delete_athlete(
            athlete_id=athlete.id,
            request=req,
            event_id=str(event_a.id),
            db=db
        )
        
        # Verify database state
        # 1. Athlete record MUST still exist (since they are still registered in Event B)
        ath_in_db = db.query(Athlete).filter(Athlete.id == athlete.id).first()
        assert ath_in_db is not None, "Athlete MUST NOT be deleted from athletes table because they are still registered in Event B"
        print("Success: Athlete still exists in athletes table.")
        
        # 2. Registration for Event A MUST be deleted
        reg_a_db = db.query(CompetitionRegistration).filter(
            CompetitionRegistration.athlete_id == athlete.id,
            CompetitionRegistration.event_id == event_a.id
        ).first()
        assert reg_a_db is None, "Registration for Event A must be deleted"
        print("Success: Registration for Event A is deleted.")
        
        # 3. Registration for Event B MUST still exist
        reg_b_db = db.query(CompetitionRegistration).filter(
            CompetitionRegistration.athlete_id == athlete.id,
            CompetitionRegistration.event_id == event_b.id
        ).first()
        assert reg_b_db is not None, "Registration for Event B must still exist"
        print("Success: Registration for Event B still exists.")
        
        # 4. Activity in Event A MUST be unlinked (athlete_id = None)
        act_a_db = db.query(Activity).filter(Activity.id == "mock_act_a_test").first()
        assert act_a_db.athlete_id is None, "Activity in Event A must be unlinked"
        print("Success: Activity in Event A is unlinked.")
        
        # 5. Activity in Event B MUST NOT be unlinked
        act_b_db = db.query(Activity).filter(Activity.id == "mock_act_b_test").first()
        assert act_b_db.athlete_id == athlete.id, "Activity in Event B must remain linked"
        print("Success: Activity in Event B remains linked.")

        # --- EXECUTE TEST CASE 2: Delete from Event B ---
        print("\n--- TEST CASE 2: Delete athlete from Event B (Last remaining event) ---")
        
        # Call the delete endpoint for event_b
        response2 = admin_delete_athlete(
            athlete_id=athlete.id,
            request=req,
            event_id=str(event_b.id),
            db=db
        )
        
        # Verify database state
        # 1. Registration for Event B MUST be deleted
        reg_b_db2 = db.query(CompetitionRegistration).filter(
            CompetitionRegistration.athlete_id == athlete.id,
            CompetitionRegistration.event_id == event_b.id
        ).first()
        assert reg_b_db2 is None, "Registration for Event B must be deleted"
        print("Success: Registration for Event B is deleted.")
        
        # 2. Athlete record MUST be deleted completely (since 0 registrations remain)
        ath_in_db2 = db.query(Athlete).filter(Athlete.id == athlete.id).first()
        assert ath_in_db2 is None, "Athlete record must be deleted completely from athletes table"
        print("Success: Athlete record is completely deleted from the database.")
        
        # 3. Activity in Event B MUST be unlinked (athlete_id = None)
        act_b_db2 = db.query(Activity).filter(Activity.id == "mock_act_b_test").first()
        assert act_b_db2.athlete_id is None, "Activity in Event B must be unlinked"
        print("Success: Activity in Event B is unlinked.")

        # --- CLEANUP ---
        db.query(Activity).filter(Activity.id.in_(["mock_act_a_test", "mock_act_b_test"])).delete(synchronize_session=False)
        db.query(CompetitionEvent).filter(CompetitionEvent.title.in_([event_a_title, event_b_title])).delete(synchronize_session=False)
        db.commit()
        print("\nCleanup completed. ALL TESTS PASSED!")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("\nAssertion or runtime error. TEST FAILED!")
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
