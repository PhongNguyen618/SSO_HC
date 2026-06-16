import sys
import os
import time

# Thêm đường dẫn thư mục gốc vào python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import Request
from backend.main import get_activities_api
from backend.database import SessionLocal, Config

db = SessionLocal()
try:
    # 1. Tìm hoặc tạo admin session trong Config
    session_id_cfg = db.query(Config).filter(Config.key == "admin_session_id").first()
    session_expiry_cfg = db.query(Config).filter(Config.key == "admin_session_expiry").first()
    admin_user_cfg = db.query(Config).filter(Config.key == "admin_username").first()
    
    token = "test_token_123456"
    expiry = str(int(time.time()) + 3600) # 1 hour from now
    
    if not session_id_cfg:
        session_id_cfg = Config(key="admin_session_id", value=token)
        db.add(session_id_cfg)
    else:
        session_id_cfg.value = token
        
    if not session_expiry_cfg:
        session_expiry_cfg = Config(key="admin_session_expiry", value=expiry)
        db.add(session_expiry_cfg)
    else:
        session_expiry_cfg.value = expiry
        
    if not admin_user_cfg:
        admin_user_cfg = Config(key="admin_username", value="admin")
        db.add(admin_user_cfg)
    else:
        admin_user_cfg.value = "admin"
        
    db.commit()
    print("Created/updated config-based admin session with token:", token)
    
    # 2. Tạo mock request
    class RealMockRequest:
        scope = {"type": "http"}
        def __init__(self, token_val):
            self._cookies = {"sso_hc_admin_session": token_val}
        @property
        def cookies(self):
            return self._cookies
            
    req = RealMockRequest(token)
    print("Calling get_activities_api...")
    res = get_activities_api(request=req, page=1, limit=20, search="", db=db)
    
    # Do get_activities_api trả về dict trực tiếp chứ không phải JSONResponse (trừ trường hợp lỗi 401)
    if isinstance(res, dict):
        print("Result status:", res.get("status"))
        print("Total activities:", res.get("total"))
        print("Activities in response:", len(res.get("activities")))
        if len(res.get("activities")) > 0:
            print("First activity keys:", res.get("activities")[0].keys())
            print("First activity data:")
            for k, v in res.get("activities")[0].items():
                print(f"  {k}: {v} (type: {type(v).__name__})")
    else:
        print("Response is not a dict:", res)
        # Nếu là JSONResponse
        import json
        try:
            print("JSONResponse body:", json.loads(res.body.decode("utf-8")))
        except Exception:
            print("Could not parse body")
            
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
