import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional, Tuple

from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db, Config

COOKIE_NAME = "sso_hc_admin_session"
ATHLETE_COOKIE_NAME = "sso_hc_athlete_session"
OAUTH_NONCE_COOKIE = "sso_hc_oauth_nonce"
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390000


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password(password: str) -> str:
    """Hash password with salted PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify current PBKDF2 hashes and legacy unsalted SHA-256 hashes."""
    if not password_hash:
        return False

    if password_hash.startswith(f"{PASSWORD_SCHEME}$"):
        try:
            _, iterations, salt_b64, digest_b64 = password_hash.split("$", 3)
            expected = _b64url_decode(digest_b64)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                _b64url_decode(salt_b64),
                int(iterations),
            )
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    # Backward compatibility for databases created before the security upgrade.
    if len(password_hash) == 64:
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, password_hash)
    return False


def needs_password_rehash(password_hash: str) -> bool:
    return not (password_hash or "").startswith(f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}$")


def _get_or_create_signing_secret(db: Session) -> str:
    row = db.query(Config).filter(Config.key == "session_signing_secret").first()
    if row and row.value and len(row.value) >= 32:
        return row.value
    secret = secrets.token_urlsafe(48)
    if row:
        row.value = secret
    else:
        db.add(Config(key="session_signing_secret", value=secret))
    db.commit()
    return secret


def _sign(secret: str, payload: str) -> str:
    return _b64url_encode(hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest())


def create_athlete_session(db: Session, athlete_id: int, max_age_seconds: int = 30 * 24 * 3600) -> str:
    exp = int(time.time()) + max_age_seconds
    payload = f"{int(athlete_id)}:{exp}"
    signature = _sign(_get_or_create_signing_secret(db), payload)
    return f"{payload}:{signature}"


def get_athlete_session(request: Request, db: Session = Depends(get_db)) -> Optional[int]:
    value = request.cookies.get(ATHLETE_COOKIE_NAME)
    if not value:
        return None
    try:
        athlete_id_s, exp_s, signature = value.split(":", 2)
        payload = f"{athlete_id_s}:{exp_s}"
        expected = _sign(_get_or_create_signing_secret(db), payload)
        if not hmac.compare_digest(signature, expected):
            return None
        if int(exp_s) < int(time.time()):
            return None
        return int(athlete_id_s)
    except (ValueError, TypeError):
        return None


def athlete_action_allowed(request: Request, db: Session, athlete_id: int) -> bool:
    if get_admin_session(request, db):
        return True
    return get_athlete_session(request, db) == int(athlete_id)


def create_oauth_state(db: Session, purpose: str, subject: str, max_age_seconds: int = 15 * 60) -> Tuple[str, str]:
    """Create a signed OAuth state and a browser-bound nonce for CSRF protection."""
    issued = int(time.time())
    nonce = secrets.token_urlsafe(24)
    raw = f"{purpose}|{subject}|{issued}|{max_age_seconds}|{nonce}"
    signature = _sign(_get_or_create_signing_secret(db), raw)
    state = _b64url_encode(f"{raw}|{signature}".encode("utf-8"))
    return state, nonce


def verify_oauth_state(request: Request, db: Session, state: str, expected_purpose: str) -> Optional[str]:
    if not state:
        return None
    try:
        decoded = _b64url_decode(state).decode("utf-8")
        purpose, subject, issued_s, max_age_s, nonce, signature = decoded.split("|", 5)
        if purpose != expected_purpose:
            return None
        raw = f"{purpose}|{subject}|{issued_s}|{max_age_s}|{nonce}"
        expected = _sign(_get_or_create_signing_secret(db), raw)
        if not hmac.compare_digest(signature, expected):
            return None
        issued = int(issued_s)
        max_age = int(max_age_s)
        now = int(time.time())
        if issued > now + 60 or now - issued > max_age:
            return None
        browser_nonce = request.cookies.get(OAUTH_NONCE_COOKIE)
        if not browser_nonce or not hmac.compare_digest(browser_nonce, nonce):
            return None
        return subject
    except Exception:
        return None


def get_admin_session(request: Request, db: Session = Depends(get_db)):
    """Return the current admin username when the signed server session is valid."""
    session_token = request.cookies.get(COOKIE_NAME)
    if not session_token:
        return None

    admin_session_id = db.query(Config).filter(Config.key == "admin_session_id").first()
    admin_session_expiry = db.query(Config).filter(Config.key == "admin_session_expiry").first()
    admin_user = db.query(Config).filter(Config.key == "admin_username").first()

    if admin_session_id and admin_session_expiry and admin_user:
        try:
            expiry_timestamp = int(admin_session_expiry.value)
            if (
                admin_session_id.value
                and hmac.compare_digest(session_token, admin_session_id.value)
                and int(time.time()) <= expiry_timestamp
            ):
                return admin_user.value
        except (ValueError, TypeError):
            pass
    return None


def admin_required(request: Request, db: Session = Depends(get_db)):
    admin = get_admin_session(request, db)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa đăng nhập quyền Admin",
        )
    return admin
