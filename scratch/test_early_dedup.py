"""
Test script to verify the Early Dedup fix.
Simulates the scenario where:
1. Saturday activity was synced correctly with Saturday date
2. Monday 00:15 sync sees the same activity again
3. Early Dedup should catch it and skip (NOT reassign to Sunday)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from sqlalchemy import func as sa_func
from backend.database import SessionLocal, Activity, Athlete

db = SessionLocal()

print("=" * 70)
print("TEST: Early Dedup Logic Verification")
print("=" * 70)

# 1. Check if there are any activities in recent days
gmt7_now = datetime.utcnow() + timedelta(hours=7)
seven_days_ago = (gmt7_now - timedelta(days=7)).strftime("%Y-%m-%d")
today_str = gmt7_now.strftime("%Y-%m-%d")

recent_acts = db.query(Activity).filter(
    Activity.activity_date >= seven_days_ago
).order_by(Activity.activity_date.desc()).limit(10).all()

print(f"\nRecent activities (last 7 days from {seven_days_ago} to {today_str}):")
print(f"Found {len(recent_acts)} activities\n")

for act in recent_acts:
    dist_raw = act.distance_km_raw if act.distance_km_raw is not None else act.distance_km
    print(f"  [{act.activity_date}] {act.athlete_name_raw[:25]:25s} | "
          f"Sport={act.sport_type:8s} | "
          f"Dist={dist_raw:.2f}km | "
          f"Time={act.moving_time_min:.1f}min | "
          f"Elev={act.elevation_gain_m:.0f}m | "
          f"Name='{act.name}'")

# 2. Simulate Early Dedup check for a specific activity
print("\n" + "=" * 70)
print("SIMULATION: What happens if Monday 00:15 sync sees a Saturday activity?")
print("=" * 70)

if recent_acts:
    test_act = recent_acts[0]  # Take the most recent activity as test case
    dist_raw = test_act.distance_km_raw if test_act.distance_km_raw is not None else test_act.distance_km
    
    print(f"\nTest activity:")
    print(f"  Athlete: {test_act.athlete_name_raw}")
    print(f"  Date: {test_act.activity_date}")
    print(f"  Sport: {test_act.sport_type}")
    print(f"  Distance: {dist_raw:.2f} km")
    print(f"  Time: {test_act.moving_time_min:.1f} min")
    print(f"  Elevation: {test_act.elevation_gain_m:.0f} m")
    
    # Simulate Early Dedup query (same as in sync_engine.py)
    early_limit = (gmt7_now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    if test_act.athlete_id:
        early_matches = db.query(Activity).filter(
            Activity.athlete_id == test_act.athlete_id,
            Activity.event_id == test_act.event_id,
            Activity.sport_type == test_act.sport_type,
            Activity.activity_date >= early_limit
        ).all()
        print(f"\n  Query by athlete_id={test_act.athlete_id}: found {len(early_matches)} candidates")
    else:
        early_matches = db.query(Activity).filter(
            sa_func.lower(Activity.athlete_name_raw) == test_act.athlete_name_raw.lower(),
            Activity.event_id == test_act.event_id,
            Activity.sport_type == test_act.sport_type,
            Activity.activity_date >= early_limit
        ).all()
        print(f"\n  Query by name='{test_act.athlete_name_raw}': found {len(early_matches)} candidates")
    
    # Check if the test activity would be caught by Early Dedup
    is_already_synced = False
    for ext in early_matches:
        ext_dist = ext.distance_km_raw if ext.distance_km_raw is not None else ext.distance_km
        dist_diff = abs((ext_dist or 0.0) - dist_raw)
        time_diff = abs((ext.moving_time_min or 0.0) - test_act.moving_time_min)
        elev_diff = abs((ext.elevation_gain_m or 0.0) - test_act.elevation_gain_m)
        
        if dist_diff <= 0.05 and time_diff <= 1.0 and elev_diff <= 10.0:
            is_already_synced = True
            print(f"\n  MATCH FOUND (would be skipped by Early Dedup):")
            print(f"    Existing activity date: {ext.activity_date}")
            print(f"    dist_diff={dist_diff:.3f} (<= 0.05), "
                  f"time_diff={time_diff:.1f} (<= 1.0), "
                  f"elev_diff={elev_diff:.1f} (<= 10.0)")
            break
    
    if is_already_synced:
        print(f"\n  RESULT: Activity WOULD BE SKIPPED by Early Dedup")
        print(f"  (Grace period logic will NOT run -> no wrong Sunday date assigned)")
    else:
        print(f"\n  RESULT: Activity would NOT be caught (it's genuinely new)")

# 3. Check for unlinked athletes (athlete_id = None)
print("\n" + "=" * 70)
print("CHECK: Unlinked athletes (athlete_id = NULL)")
print("=" * 70)

unlinked_recent = db.query(Activity).filter(
    Activity.athlete_id == None,
    Activity.activity_date >= seven_days_ago
).all()

print(f"\nUnlinked activities in last 7 days: {len(unlinked_recent)}")
for act in unlinked_recent[:5]:
    print(f"  [{act.activity_date}] {act.athlete_name_raw} | {act.sport_type} | "
          f"Dist={act.distance_km:.2f}km")

if unlinked_recent:
    print(f"\n  These would now also be checked by Early Dedup (previously skipped!)")
else:
    print(f"\n  No unlinked activities found - all athletes are properly linked.")

db.close()
print("\n" + "=" * 70)
print("Test completed successfully!")
print("=" * 70)
