"""
Auth Router — /api/auth/*
Includes: register, login (with history tracking), me, logout,
          admin endpoints: /admin/users, /admin/login-history
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from services.auth_service import (
    authenticate_user, create_user, decode_token,
    get_user_by_id, create_token, get_all_users,
    get_login_history, get_user_login_history, record_login
)

router  = APIRouter()
bearer  = HTTPBearer(auto_error=False)

# ─── SCHEMAS ────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

# ─── AUTH DEPENDENCY ────────────────────────────────────────────────────────
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await get_user_by_id(int(payload.get("sub", 0)))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ─── PUBLIC ROUTES ───────────────────────────────────────────────────────────
@router.post("/auth/register")
async def register(body: RegisterRequest, request: Request):
    """Register a new user account."""
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if len(body.username.strip()) < 2:
        raise HTTPException(400, "Username must be at least 2 characters")
    try:
        user  = await create_user(body.email.lower().strip(), body.username.strip(), body.password)
        token = create_token({"sub": str(user["id"]), "email": user["email"]})

        # Record the registration as a login event
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        ua = request.headers.get("user-agent", "")
        await record_login(user["id"], user["email"], user["username"], ip, ua)

        return {
            "access_token": token,
            "token_type":   "bearer",
            "user": {"id": user["id"], "email": user["email"], "username": user["username"]}
        }
    except ValueError as e:
        raise HTTPException(409, str(e))

@router.post("/auth/login")
async def login(body: LoginRequest, request: Request):
    """Login with email + password. Records login event with IP."""
    user = await authenticate_user(body.email.lower().strip(), body.password)
    if not user:
        raise HTTPException(401, "Invalid email or password")

    token = create_token({"sub": str(user["id"]), "email": user["email"]})

    # 📝 Record login history
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    ua = request.headers.get("user-agent", "")
    await record_login(user["id"], user["email"], user["username"], ip, ua)

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user": {"id": user["id"], "email": user["email"], "username": user["username"]}
    }

@router.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Get current logged-in user's info."""
    history = await get_user_login_history(current_user["id"], limit=5)
    return {
        "id":         current_user["id"],
        "email":      current_user["email"],
        "username":   current_user["username"],
        "created_at": str(current_user.get("created_at", "")),
        "last_logins": [
            {
                "ip":        r["ip_address"],
                "logged_in": str(r["logged_in_at"])
            } for r in history
        ]
    }

# ─── ADMIN ROUTES ─────────────────────────────────────────────────────────
# NOTE: In production you'd protect these with an admin role check.
# For now they require any valid JWT token.

@router.get("/auth/admin/users")
async def admin_users(current_user: dict = Depends(get_current_user)):
    """List all registered users (admin view)."""
    users = await get_all_users()
    return {
        "total": len(users),
        "users": [
            {
                "id":         u["id"],
                "email":      u["email"],
                "username":   u["username"],
                "joined":     str(u["created_at"])
            } for u in users
        ]
    }

@router.get("/auth/admin/login-history")
async def admin_login_history(current_user: dict = Depends(get_current_user)):
    """Full login history — who logged in, when, from where."""
    history = await get_login_history(limit=100)
    return {
        "total": len(history),
        "history": [
            {
                "id":         r["id"],
                "email":      r["email"],
                "username":   r["username"],
                "ip_address": r["ip_address"],
                "browser":    _parse_browser(r.get("user_agent", "")),
                "logged_in":  str(r["logged_in_at"])
            } for r in history
        ]
    }

def _parse_browser(ua: str) -> str:
    """Very simple browser name extraction from user-agent."""
    ua = ua or ""
    if "Chrome"  in ua and "Edg"  not in ua: return "Chrome"
    if "Firefox" in ua: return "Firefox"
    if "Safari"  in ua and "Chrome" not in ua: return "Safari"
    if "Edg"     in ua: return "Edge"
    if "bot"     in ua.lower(): return "Bot"
    return "Unknown"
