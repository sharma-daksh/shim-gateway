"""
Authentication and Authorization module for SHIM.
Provides PBKDF2-HMAC-SHA256 password hashing, secure token generation, and role checks.
"""
import hashlib
import hmac
import secrets
import base64
import json
import time
from typing import Dict, Any, Optional, Tuple
from fastapi import HTTPException, Header, Depends
from database import get_connection, DB_PATH, get_project_by_api_key

SECRET_KEY = "shim-super-secure-liquid-chrome-secret-token-key"
SALT_BYTES = 16
HASH_ROUNDS = 100000

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a unique random salt."""
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ROUNDS)
    return f"{base64.b64encode(salt).decode('utf-8')}${base64.b64encode(derived).decode('utf-8')}"

def verify_password(password: str, hashed: str) -> bool:
    """Constant-time verification of password against stored hash."""
    try:
        salt_b64, derived_b64 = hashed.split("$")
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        expected_derived = base64.b64decode(derived_b64.encode("utf-8"))
        actual_derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ROUNDS)
        return hmac.compare_digest(expected_derived, actual_derived)
    except Exception:
        return False

def create_session_token(user_id: str, username: str, role: str, expires_in: int = 86400) -> str:
    """Create a tamper-evident signed token (HMAC-SHA256 signature)."""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": time.time() + expires_in
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify signed token signature and expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload_raw = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_raw)
        if time.time() > payload.get("exp", 0):
            return None # Expired
        return payload
    except Exception:
        return None

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Dependency to extract authenticated user from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required: Missing or invalid Bearer token")
    token = authorization.split(" ")[1]
    payload = verify_session_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")
    return payload

def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency to restrict endpoints to Administrator role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Administrator access required")
    return user
