import os
import sys
import logging
from app.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
    SMTP_USER, SMTP_PASSWORD, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET,
    UPI_ID, JWT_SECRET
)

logger = logging.getLogger(__name__)

def validate_env_variables():
    """Validate required environment variables"""
    required_vars = {
        'GOOGLE_CLIENT_ID': GOOGLE_CLIENT_ID,
        'GOOGLE_CLIENT_SECRET': GOOGLE_CLIENT_SECRET,
        'GOOGLE_REDIRECT_URI': GOOGLE_REDIRECT_URI,
        'SMTP_USER': SMTP_USER,
        'SMTP_PASSWORD': SMTP_PASSWORD,
        'PAYPAL_CLIENT_ID': PAYPAL_CLIENT_ID,
        'PAYPAL_CLIENT_SECRET': PAYPAL_CLIENT_SECRET,
        'UPI_ID': UPI_ID,
        'JWT_SECRET': JWT_SECRET
    }
    
    missing_vars = []
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing_vars.append(var_name)
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        # For development, just log warning instead of exiting
        logger.warning("Some environment variables are missing. Please check your .env file.")
        return False
    
    logger.info("All required environment variables are set")
    return True

def get_env_or_default(key: str, default: str = None) -> str:
    """Get environment variable with default value"""
    return os.getenv(key, default)
