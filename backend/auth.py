import hashlib
from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from backend.database import get_db, Config

COOKIE_NAME = "sso_hc_admin_session"

def verify_password(password: str, password_hash: str) -> bool:
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash

def get_admin_session(request: Request, db: Session = Depends(get_db)):
    """
    Dependency kiểm tra trạng thái đăng nhập của Admin.
    Nếu chưa đăng nhập, trả về None hoặc ném lỗi tùy endpoint.
    """
    import time
    session_token = request.cookies.get(COOKIE_NAME)
    if not session_token:
        return None
    
    # Kiểm tra session động trong DB config
    admin_session_id = db.query(Config).filter(Config.key == "admin_session_id").first()
    admin_session_expiry = db.query(Config).filter(Config.key == "admin_session_expiry").first()
    admin_user = db.query(Config).filter(Config.key == "admin_username").first()
    
    if admin_session_id and admin_session_expiry and admin_user:
        try:
            expiry_timestamp = int(admin_session_expiry.value)
            if session_token == admin_session_id.value and int(time.time()) <= expiry_timestamp:
                return admin_user.value
        except (ValueError, TypeError):
            pass
            
    return None

def admin_required(request: Request, db: Session = Depends(get_db)):
    """
    Dependency yêu cầu phải đăng nhập admin, nếu chưa sẽ redirect về trang login.
    """
    admin = get_admin_session(request, db)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa đăng nhập quyền Admin"
        )
    return admin
