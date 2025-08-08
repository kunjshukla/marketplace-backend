from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

def create_oauth_flow():
    """Create Google OAuth flow"""
    try:
        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=["openid", "email", "profile"],
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        
        return flow
        
    except Exception as e:
        logger.error(f"Error creating OAuth flow: {e}")
        return None

def verify_google_token(token: str) -> dict:
    """Verify Google ID token"""
    try:
        idinfo = id_token.verify_oauth2_token(
            token, 
            Request(), 
            settings.GOOGLE_CLIENT_ID
        )
        
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')
        
        return idinfo
        
    except Exception as e:
        logger.error(f"Error verifying Google token: {e}")
        return None
