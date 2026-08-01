"""
Auth Router — /api/auth/*
Endpoints: register, login, me, logout (client-side)
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from services.auth_service import (
    authenticate_user, create_user, decode_token,
    get_user_by_id, create_token
)

router = APIRouter()
bearer = HTTPBearer(auto_error=False)

# ─── SCHEMAS ───────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

# ─── DEPENDENCY — get current user from token ──────────────────────────────
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

# ─── ROUTES ────────────────────────────────────────────────────────────────
@router.post("/auth/register")
async def register(body: RegisterRequest):
    """Register a new user account."""
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if len(body.username.strip()) < 2:
        raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
    try:
        user = await create_user(body.email.lower().strip(), body.username.strip(), body.password)
        token = create_token({"sub": str(user["id"]), "email": user["email"]})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user["id"], "email": user["email"], "username": user["username"]}
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/auth/login")
async def login(body: LoginRequest):
    """Login with email and password, returns JWT token."""
    user = await authenticate_user(body.email.lower().strip(), body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token({"sub": str(user["id"]), "email": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"], "username": user["username"]}
    }

@router.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Get current logged-in user info."""
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "username": current_user["username"],
        "created_at": current_user.get("created_at")
    }
