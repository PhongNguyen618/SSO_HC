"""Test export_rewards_excel directly by calling the controller function with mock parameters."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import export_rewards_excel
from backend.database import SessionLocal
from fastapi import Request

# Create a mock Request
class MockRequest:
    def __init__(self):
        self.cookies = {"admin_session": "mock_session_id"}
        self.headers = {}
        
    def get(self, key, default=None):
        return self.cookies.get(key, default)

# We can patch get_admin_session in main.py to always return True for testing
import backend.main
original_get_admin_session = backend.main.get_admin_session
backend.main.get_admin_session = lambda req, db: True

import asyncio

async def run_test():
    db = SessionLocal()
    try:
        print("Testing export_rewards_excel for event_id=1...")
        req = MockRequest()
        response = export_rewards_excel(request=req, event_id="1", db=db)
        
        # Check response type and headers
        print(f"Response status/type: {type(response)}")
        print(f"Headers: {response.headers}")
        
        # Read the bytes returned
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        content = b"".join(chunks)
        print(f"Excel file size: {len(content)} bytes")
        
        # Try reading it with pandas to check structure
        import pandas as pd
        excel_file = io.BytesIO(content)
        
        sheets = ["Tổng quan & Bộ môn", "BXH Phòng ban", "BXH Run-Walk", "Tỷ lệ tham gia các đơn vị", "Chi tiết nhận thưởng"]
        for sheet in sheets:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            print(f"  ✅ Sheet '{sheet}' is valid. Shape: {df.shape}")
            
        print("\n🎉 ALL SHEETS RENDERED AND READ BACK SUCCESSFULLY!")
        
    except Exception as e:
        print(f"❌ ERROR testing export endpoint: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore original function
        backend.main.get_admin_session = original_get_admin_session
        db.close()

if __name__ == "__main__":
    asyncio.run(run_test())
