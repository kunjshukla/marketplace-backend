from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
import httpx
import secrets
import logging
from datetime import datetime
import jwt
import base64
import json

from db.session import get_db
from models.user import User
from schemas.user import UserResponse, TokenResponse, UserUpdate
from core.auth import create_access_token, create_refresh_token, verify_token, get_current_user
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth state storage (in production, use Redis)
oauth_states = {}

@router.get("/login-google")
async def login_google():
    """Initiate Google OAuth login"""
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {"created_at": datetime.utcnow()}

    # Use Google OAuth v2 endpoint and request offline access for refresh tokens
    authorization_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        f"scope=openid%20email%20profile&"
        f"response_type=code&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"state={state}"
    )

    return {
        "success": True,
        "message": "Authorization URL generated",
        "data": {"authorization_url": authorization_url}
    }

@router.post("/google/callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback - supports both OAuth codes and JWT credentials"""
    try:
        body = await request.json()
        
        # Check if we have a JWT credential (Google Identity Services)
        credential = body.get("credential")
        oauth_code = body.get("code")
        
        user_info = None
        
        if credential:
            # Handle Google Identity Services JWT credential
            try:
                # Decode without verification first to get header
                header = jwt.get_unverified_header(credential)
                
                # Get Google's public keys to verify the JWT
                async with httpx.AsyncClient() as client:
                    keys_response = await client.get("https://www.googleapis.com/oauth2/v3/certs")
                    keys = keys_response.json()
                
                # Find the key that matches the JWT's kid
                key = None
                for k in keys["keys"]:
                    if k["kid"] == header["kid"]:
                        key = jwt.algorithms.RSAAlgorithm.from_jwk(k)
                        break
                
                if not key:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid JWT key"
                    )
                
                # Verify and decode the JWT
                payload = jwt.decode(
                    credential,
                    key,
                    algorithms=["RS256"],
                    audience=settings.GOOGLE_CLIENT_ID
                )
                
                # Extract user info from JWT payload
                user_info = {
                    "id": payload.get("sub"),
                    "email": payload.get("email"),
                    "name": payload.get("name"),
                    "picture": payload.get("picture"),
                    "email_verified": payload.get("email_verified", False)
                }
                
            except jwt.InvalidTokenError as e:
                logger.error(f"JWT verification failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Google credential"
                )
                
        elif oauth_code:
            # Handle traditional OAuth authorization code
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": oauth_code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            }

            async with httpx.AsyncClient() as client:
                token_response = await client.post(token_url, data=token_data)

            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange code for tokens"
                )

            tokens = token_response.json()
            access_token = tokens.get("access_token")

            # Get user info from Google
            user_info_url = f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={access_token}"

            async with httpx.AsyncClient() as client:
                user_response = await client.get(user_info_url)

            if user_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user information"
                )

            user_info = user_response.json()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either credential or code is required"
            )
        
        if not user_info or not user_info.get("id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user information from Google"
            )

        # Check if user exists
        user = db.query(User).filter(User.google_id == user_info["id"]).first()

        if not user:
            # Create new user
            user = User(
                name=user_info.get("name", ""),
                email=user_info.get("email", ""),
                google_id=user_info["id"],
                profile_pic=user_info.get("picture"),
                role="user"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new user: {user.email}")

        # Create JWT tokens
        jwt_access_token = create_access_token({"user_id": user.id, "email": user.email})
        jwt_refresh_token = create_refresh_token({"user_id": user.id})

        # Update user's refresh token
        user.refresh_token = jwt_refresh_token
        db.commit()

        return {
            "success": True,
            "message": "Authentication successful",
            "data": {
                "access_token": jwt_access_token,
                "refresh_token": jwt_refresh_token,
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "profile_pic": user.profile_pic,
                    "role": user.role
                }
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


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
