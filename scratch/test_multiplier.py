"""
Test script for EventMultiplier feature.
Verifies:
1. get_multiplier_for_date() works correctly
2. EventMultiplier CRUD operations
3. calculate_kcal with multiplier
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal, EventMultiplier, Activity, CompetitionEvent, init_db
from backend.calculations import get_multiplier_for_date, calculate_kcal

print("=" * 60)
print("TEST: EventMultiplier Feature")
print("=" * 60)

db = SessionLocal()

try:
    # 1. Test calculate_kcal with multiplier
    print("\n--- Test 1: calculate_kcal with multiplier ---")
    kcal_normal = calculate_kcal(8.0, 65.0, 30.0, 0.0, "Run", multiplier=1.0)
    kcal_x2 = calculate_kcal(8.0, 65.0, 30.0, 0.0, "Run", multiplier=2.0)
    kcal_x15 = calculate_kcal(8.0, 65.0, 30.0, 0.0, "Run", multiplier=1.5)
    print(f"  KCAL (x1.0): {kcal_normal}")
    print(f"  KCAL (x2.0): {kcal_x2}")
    print(f"  KCAL (x1.5): {kcal_x15}")
    assert kcal_x2 == kcal_normal * 2, f"Expected {kcal_normal * 2}, got {kcal_x2}"
    print("  PASS: Multiplier correctly applied to calculate_kcal")
    
    # 2. Test get_multiplier_for_date with no config
    print("\n--- Test 2: get_multiplier_for_date (no config) ---")
    result = get_multiplier_for_date("2025-06-15", 999, db)
    print(f"  Multiplier for unknown event: {result}")
    assert result == 1.0, f"Expected 1.0, got {result}"
    print("  PASS: Returns 1.0 when no config exists")
    
    # 3. Find an active competition for testing
    print("\n--- Test 3: Testing with active competition ---")
    comp = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).first()
    if comp:
        print(f"  Found active competition: {comp.title} (ID: {comp.id})")
        
        # Clean up any test multipliers
        db.query(EventMultiplier).filter(
            EventMultiplier.event_id == comp.id,
            EventMultiplier.description.like("%TEST_MULTIPLIER%")
        ).delete(synchronize_session=False)
        db.commit()
        
        # Add test multiplier for Sunday (day_of_week=6)
        test_dow = EventMultiplier(
            event_id=comp.id,
            day_of_week=6,  # Sunday
            special_date=None,
            multiplier=2.0,
            description="TEST_MULTIPLIER: x2 Sunday"
        )
        db.add(test_dow)
        
        # Add test multiplier for specific date 2025-01-01
        test_special = EventMultiplier(
            event_id=comp.id,
            day_of_week=None,
            special_date="2025-01-01",
            multiplier=3.0,
            description="TEST_MULTIPLIER: x3 New Year"
        )
        db.add(test_special)
        db.commit()
        print("  Added test multipliers: Sunday x2, 2025-01-01 x3")
        
        # Test Sunday (2025-06-15 is a Sunday)
        result_sun = get_multiplier_for_date("2025-06-15", comp.id, db)
        print(f"  Multiplier for Sunday 2025-06-15: {result_sun}")
        assert result_sun == 2.0, f"Expected 2.0, got {result_sun}"
        print("  PASS: Sunday multiplier works")
        
        # Test Monday (2025-06-16 is a Monday)
        result_mon = get_multiplier_for_date("2025-06-16", comp.id, db)
        print(f"  Multiplier for Monday 2025-06-16: {result_mon}")
        assert result_mon == 1.0, f"Expected 1.0, got {result_mon}"
        print("  PASS: Weekday without config returns 1.0")
        
        # Test special date (2025-01-01 is a Wednesday)
        result_special = get_multiplier_for_date("2025-01-01", comp.id, db)
        print(f"  Multiplier for 2025-01-01 (special): {result_special}")
        assert result_special == 3.0, f"Expected 3.0, got {result_special}"
        print("  PASS: Special date multiplier works and takes priority")
        
        # Test no event_id
        result_no_event = get_multiplier_for_date("2025-06-15", None, db)
        print(f"  Multiplier with no event_id: {result_no_event}")
        assert result_no_event == 1.0, f"Expected 1.0, got {result_no_event}"
        print("  PASS: Returns 1.0 when event_id is None")
        
        # Clean up test data
        db.query(EventMultiplier).filter(
            EventMultiplier.description.like("%TEST_MULTIPLIER%")
        ).delete(synchronize_session=False)
        db.commit()
        print("  Cleaned up test multipliers")
    else:
        print("  WARNING: No active competition found. Skipping integration tests.")
    
    # 4. Check Activity model has multiplier columns
    print("\n--- Test 4: Activity model columns ---")
    from sqlalchemy import inspect
    from backend.database import engine
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('activities')]
    assert 'multiplier' in columns, "multiplier column missing from activities"
    assert 'kcal_burned_raw' in columns, "kcal_burned_raw column missing from activities"
    print(f"  Activity columns include: multiplier, kcal_burned_raw")
    print("  PASS: Activity model has correct columns")
    
    # 5. Check EventMultiplier table exists
    print("\n--- Test 5: EventMultiplier table ---")
    tables = inspector.get_table_names()
    assert 'event_multipliers' in tables, "event_multipliers table missing"
    em_cols = [c['name'] for c in inspector.get_columns('event_multipliers')]
    print(f"  EventMultiplier columns: {em_cols}")
    assert 'special_date' in em_cols
    assert 'day_of_week' in em_cols
    assert 'multiplier' in em_cols
    print("  PASS: EventMultiplier table exists with correct columns")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    
except Exception as e:
    print(f"\nTEST FAILED: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
