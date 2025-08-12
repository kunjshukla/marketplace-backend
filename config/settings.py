import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from the backend .env explicitly (works regardless of cwd)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

class Settings(BaseSettings):
    """Application settings"""
    
    # Base directory
    BASE_DIR: Path = Path(__file__).parent.parent
    
    # Database - Supabase PostgreSQL (fallback to local SQLite if not provided)
    DATABASE_URL: str = os.getenv("DATABASE_URL") or "sqlite:///./nft_marketplace.db"
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    @property
    def DATABASE_URL_ASYNC(self) -> str:
        """Get async database URL with asyncpg driver"""
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL
        return self.DATABASE_URL
    
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Get sync database URL with psycopg2 driver"""
        if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
        return self.DATABASE_URL
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    # Default to 'postmessage' to support GIS popup code flow (server exchanges with redirect_uri=postmessage)
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "postmessage")
    GOOGLE_ALLOWED_DOMAIN: str = os.getenv("GOOGLE_ALLOWED_DOMAIN", "")  # Optional: restrict to single domain
    
    # Email/SMTP
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # Frontend Base URL (for magic link callbacks)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # PayPal (new unified base variable; keep old PAYPAL_BASE_URL for backward compatibility)
    PAYPAL_CLIENT_ID: str = os.getenv("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET: str = os.getenv("PAYPAL_CLIENT_SECRET", "")
    PAYPAL_WEBHOOK_ID: str = os.getenv("PAYPAL_WEBHOOK_ID", "")
    PAYPAL_BASE: str = os.getenv("PAYPAL_BASE", "https://api-m.sandbox.paypal.com")  # prod: https://api-m.paypal.com
    PAYPAL_BASE_URL: str = os.getenv("PAYPAL_BASE_URL", "https://api.sandbox.paypal.com")  # legacy
    
    @property
    def EFFECTIVE_PAYPAL_BASE(self) -> str:
        return self.PAYPAL_BASE or self.PAYPAL_BASE_URL
    
    # Google Form logging (optional)
    GOOGLE_FORM_URL: str = os.getenv("GOOGLE_FORM_URL", "")
    GF_ENTRY_NAME: str = os.getenv("GF_ENTRY_NAME", "")
    GF_ENTRY_EMAIL: str = os.getenv("GF_ENTRY_EMAIL", "")
    GF_ENTRY_NFT_ID: str = os.getenv("GF_ENTRY_NFT_ID", "")
    GF_ENTRY_METHOD: str = os.getenv("GF_ENTRY_METHOD", "")
    GF_ENTRY_TXN: str = os.getenv("GF_ENTRY_TXN", "")
    
    # UPI
    UPI_ID: str = os.getenv("UPI_ID", "")
    UPI_PAYEE_NAME: str = os.getenv("UPI_PAYEE_NAME", "")
    
    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key-here")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION: int = 3600  # 1 hour
    REFRESH_TOKEN_EXPIRATION: int = 7 * 24 * 3600  # 7 days
    
    # Thirdweb (optional)
    THIRDWEB_CLIENT_ID: str = os.getenv("THIRDWEB_CLIENT_ID", "")
    
    # CORS - Updated for development and production
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://vercel.app",
        "https://*.vercel.app",
        "https://netlify.app", 
        "https://*.netlify.app"
    ]
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

# Create global settings instance
settings = Settings()
