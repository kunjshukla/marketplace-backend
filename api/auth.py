from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
import logging
import httpx  # Added for token exchange

from db.session import get_db
from models.user import User
from schemas.user import UserResponse, TokenResponse, UserUpdate
from core.auth import create_access_token, create_refresh_token, verify_token, get_current_user
from config.settings import settings

# New imports for simplified Google token verification
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from utilities.smtp import send_email
from jose import jwt

MAGIC_LINK_EXPIRY_MINUTES = 15

class RequestMagicLinkIn(BaseModel):
    email: EmailStr

class VerifyMagicLinkIn(BaseModel):
    token: str

def create_magic_link_token(email: str) -> str:
    payload = {
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES),
        "type": "magic_link"
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def verify_magic_link_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "magic_link":
            raise HTTPException(status_code=400, detail="Invalid token type")
        return payload["email"]
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid or expired link")

@router.post("/request-link")
async def request_magic_link(data: RequestMagicLinkIn, db: Session = Depends(get_db)):
    """Send magic login link to email"""
    token = create_magic_link_token(data.email)
    link = f"{settings.FRONTEND_URL.rstrip('/')}/login?token={token}"
    html = f"""
    <p>Click to log in:</p>
    <p><a href="{link}">{link}</a></p>
    <p>This link expires in {MAGIC_LINK_EXPIRY_MINUTES} minutes.</p>
    """
    # Ensure user exists or create basic record
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        user = User(name=data.email.split('@')[0], email=data.email, google_id=f"magic_{data.email}", role="user")
        db.add(user)
        db.commit()
        db.refresh(user)
    if not send_email(data.email, "Your Magic Login Link", html):
        raise HTTPException(status_code=500, detail="Failed to send email")
    return {"success": True, "message": "Magic link sent"}

@router.post("/verify-link")
async def verify_magic_link(data: VerifyMagicLinkIn, db: Session = Depends(get_db)):
    """Verify magic link token and issue session JWTs"""
    email = verify_magic_link_token(data.token)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Should not happen since we create on request-link, but handle gracefully
        user = User(name=email.split('@')[0], email=email, google_id=f"magic_{email}", role="user")
        db.add(user)
        db.commit()
        db.refresh(user)
    access_token = create_access_token({"user_id": user.id, "email": user.email})
    refresh_token = create_refresh_token({"user_id": user.id})
    user.refresh_token = refresh_token
    db.commit()
    return {
        "success": True,
        "message": "Authentication successful",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "profile_pic": user.profile_pic,
                "role": user.role
            }
        }
    }


# Removed legacy OAuth state storage and endpoints (/login-google, /google/callback)
# Keep only the direct One Tap credential endpoint.

@router.post("/google", summary="Direct Google Sign-In (One Tap / Credential)")
async def google_direct_sign_in(payload: dict, db: Session = Depends(get_db)):
    """Accepts { credential: <google id token> } and returns access/refresh tokens."""
    credential = payload.get("credential")
    if not credential:
        raise HTTPException(status_code=400, detail="Missing Google credential")
    try:
        idinfo = google_id_token.verify_oauth2_token(credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
    except Exception as e:
        logger.warning(f"Google token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google token")

    # Hardening checks
    if idinfo.get("aud") != settings.GOOGLE_CLIENT_ID:
        logger.warning("Google token audience mismatch")
        raise HTTPException(status_code=401, detail="Invalid Google token audience")
    if idinfo.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        logger.warning("Google token issuer invalid")
        raise HTTPException(status_code=401, detail="Invalid Google token issuer")
    if not idinfo.get("email_verified"):
        logger.warning("Unverified Google account email rejected")
        raise HTTPException(status_code=401, detail="Email not verified with Google")
    if settings.GOOGLE_ALLOWED_DOMAIN:
        email_val = idinfo.get("email", "") or ""
        if not email_val.endswith(f"@{settings.GOOGLE_ALLOWED_DOMAIN}"):
            logger.warning("Google account domain not allowed")
            raise HTTPException(status_code=403, detail="Email domain not allowed")

    google_sub = idinfo.get("sub")
    email = idinfo.get("email")
    name = idinfo.get("name") or ""
    picture = idinfo.get("picture")

    if not google_sub:
        raise HTTPException(status_code=400, detail="Invalid Google token payload")

    # Upsert user
    user = db.query(User).filter(User.google_id == google_sub).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            name=name,
            email=email or f"user_{google_sub}@example.com",
            google_id=google_sub,
            profile_pic=picture,
            role="user"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user via direct Google sign-in: {user.email}")
    else:
        # Ensure google_id attached
        if not user.google_id:
            user.google_id = google_sub
            db.commit()

    access_token = create_access_token({"user_id": user.id, "email": user.email})
    refresh_token = create_refresh_token({"user_id": user.id})
    user.refresh_token = refresh_token
    db.commit()

    return {
        "success": True,
        "message": "Authentication successful",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "profile_pic": user.profile_pic,
                "role": user.role
            }
        }
    }

@router.post("/google/code", summary="Google OAuth Code Exchange (DISABLED)")
async def google_code_exchange(payload: dict, db: Session = Depends(get_db)):
    """(Disabled) Previously accepted { code: <authorization_code> }.
    OAuth authorization code flow has been disabled in favor of One Tap / ID token popup only.
    """
    raise HTTPException(status_code=410, detail="Google OAuth code flow disabled. Use direct credential endpoint /api/auth/google.")

# (Original implementation removed for security / simplification.)

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Return current authenticated user's profile"""
    return current_user

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    if updates.name is not None:
        current_user.name = updates.name
    if updates.profile_pic is not None:
        current_user.profile_pic = updates.profile_pic
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout user"""
    current_user.refresh_token = None
    db.commit()

    return {
        "success": True,
        "message": "Successfully logged out",
        "data": None
    }
