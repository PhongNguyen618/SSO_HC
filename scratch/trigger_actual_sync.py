import sys
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from backend.database import SessionLocal
from backend.sync_engine import sync_club_activities
import traceback

def run_sync():
    print("Triggering sync_club_activities() manually via script...")
    try:
        res = sync_club_activities()
        print("Sync results:", res)
    except Exception as e:
        print("Sync threw exception:")
        traceback.print_exc()

if __name__ == "__main__":
    run_sync()
