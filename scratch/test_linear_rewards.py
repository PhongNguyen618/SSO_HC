import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal, CompetitionEvent
from backend.calculations import get_award_info

db = SessionLocal()
try:
    # 1. Tạo giải đấu mock với reward_type là 'linear'
    mock_event = CompetitionEvent(
        title="Linear Reward Test Event",
        start_date="2026-06-01",
        end_date="2026-06-30",
        is_active=True,
        reward_type="linear",
        reward_linear_kcal=100.0,
        reward_linear_amount=5000.0
    )
    db.add(mock_event)
    db.commit()
    db.refresh(mock_event)
    print("Created mock linear event with ID:", mock_event.id)
    
    # 2. Kiểm thử get_award_info
    # Test case 1: kcal < 100
    res1 = get_award_info(gender="Nam", total_kcal=50.0, db=db, event_id=mock_event.id)
    print("KCAL = 50: Reward =", res1["reward_amount"], "VND, Next Threshold =", res1["next_threshold"], "KCAL")
    assert res1["reward_amount"] == 0.0
    assert res1["next_threshold"] == 100.0
    
    # Test case 2: kcal = 100
    res2 = get_award_info(gender="Nam", total_kcal=100.0, db=db, event_id=mock_event.id)
    print("KCAL = 100: Reward =", res2["reward_amount"], "VND, Next Threshold =", res2["next_threshold"], "KCAL")
    assert res2["reward_amount"] == 5000.0
    assert res2["next_threshold"] == 200.0
    
    # Test case 3: kcal = 150
    res3 = get_award_info(gender="Nam", total_kcal=150.0, db=db, event_id=mock_event.id)
    print("KCAL = 150: Reward =", res3["reward_amount"], "VND, Next Threshold =", res3["next_threshold"], "KCAL")
    assert res3["reward_amount"] == 5000.0
    assert res3["next_threshold"] == 200.0
    
    # Test case 4: kcal = 205
    res4 = get_award_info(gender="Nam", total_kcal=205.0, db=db, event_id=mock_event.id)
    print("KCAL = 205: Reward =", res4["reward_amount"], "VND, Next Threshold =", res4["next_threshold"], "KCAL")
    assert res4["reward_amount"] == 10000.0
    assert res4["next_threshold"] == 300.0
    
    # Dọn dẹp
    db.delete(mock_event)
    db.commit()
    print("Cleanup completed. Linear reward test: SUCCESS!")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Linear reward test: FAILED!")
finally:
    db.close()
