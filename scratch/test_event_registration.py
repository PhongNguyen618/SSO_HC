import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal, Athlete, CompetitionEvent, CompetitionRegistration
from fastapi import Request

db = SessionLocal()
try:
    # 1. Tim hoac tao giai dau dang hoat dong
    event = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).first()
    if not event:
        event = CompetitionEvent(
            title="Giai Chay Test",
            start_date="2026-06-01",
            end_date="2026-06-30",
            is_active=True
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        print("Created mock event:", event.title)
    else:
        print("Using existing active event:", event.title)
        
    event_id = event.id
    
    # 2. Xoa VDV test cu neu co
    test_strava_name = "athlete_test_registration_unique_name"
    old_athlete = db.query(Athlete).filter(Athlete.strava_name == test_strava_name).first()
    if old_athlete:
        # Xoa cac dang ky
        db.query(CompetitionRegistration).filter(CompetitionRegistration.athlete_id == old_athlete.id).delete()
        db.delete(old_athlete)
        db.commit()
        print("Cleaned up old test athlete.")
        
    # 3. Goi truc tiep backend.main.register_athlete
    from backend.main import register_athlete
    
    class MockURL:
        path = "/register"
        
    class RealMockRequest:
        scope = {"type": "http"}
        url = MockURL()
        
    req = RealMockRequest()
    print("TEST CASE 1: Register new Athlete")
    res = register_athlete(
        request=req,
        full_name="VDV Chay Test 1",
        gender="Nam",
        department="PHONG KY THUAT",
        weight=70.0,
        strava_name=test_strava_name,
        event_id=event_id,
        is_update="false",
        db=db
    )
    
    # Kiem tra VDV moi trong DB
    new_athlete = db.query(Athlete).filter(Athlete.strava_name == test_strava_name).first()
    assert new_athlete is not None, "Athlete should be created"
    print(f"Success: Created athlete with ID {new_athlete.id}")
    
    # Kiem tra dang ky giai dau
    reg = db.query(CompetitionRegistration).filter(
        CompetitionRegistration.athlete_id == new_athlete.id,
        CompetitionRegistration.event_id == event_id
    ).first()
    assert reg is not None, "Registration record should exist"
    print("Success: Registered athlete for event successfully.")
    
    # --- TEST CASE 2: Register existing Strava name but is_update="true" ---
    print("TEST CASE 2: Update existing Athlete")
    res = register_athlete(
        request=req,
        full_name="VDV Chay Test 1",
        gender="Nam",
        department="PHONG HANH CHINH NHAN SU",
        weight=65.0,
        strava_name=test_strava_name,
        event_id=event_id,
        is_update="true",
        db=db
    )
    
    # Refresh VDV
    db.refresh(new_athlete)
    assert new_athlete.weight == 65.0, "Weight should be updated"
    assert new_athlete.department == "PHONG HANH CHINH NHAN SU", "Department should be updated"
    print(f"Success: Updated athlete successfully (New Weight: {new_athlete.weight})")
    
    # Kiem tra rang van dang ky duoc duy tri
    reg = db.query(CompetitionRegistration).filter(
        CompetitionRegistration.athlete_id == new_athlete.id,
        CompetitionRegistration.event_id == event_id
    ).first()
    assert reg is not None, "Registration should persist"
    print("Success: Registration persists after update.")
    
    # Don dep du lieu
    db.query(CompetitionRegistration).filter(CompetitionRegistration.athlete_id == new_athlete.id).delete()
    db.delete(new_athlete)
    db.commit()
    print("Cleanup completed. Test SUCCESS!")
    
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Test FAILED!")
finally:
    db.close()
