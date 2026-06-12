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
    session_token = request.cookies.get(COOKIE_NAME)
    if not session_token:
        return None
    
    # Kiểm tra xem session_token có trùng khớp với cấu hình trong DB không
    admin_user = db.query(Config).filter(Config.key == "admin_username").first()
    admin_pass = db.query(Config).filter(Config.key == "admin_password_hash").first()
    
    if not admin_user or not admin_pass:
        return None
        
    # Tạo token mong đợi (để kiểm tra khớp)
    expected_token = hashlib.sha256(f"{admin_user.value}_{admin_pass.value}".encode("utf-8")).hexdigest()
    if session_token == expected_token:
        return admin_user.value
        
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
