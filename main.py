from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os
from decimal import Decimal

from config.settings import settings
from db.session import create_tables, SessionLocal, engine
from utilities.jwt import validate_env_variables
from models.nft import NFT
from sqlalchemy import inspect, text
from fastapi.openapi.utils import get_openapi

# Import API routers
from api.auth import router as auth_router
from api.nft import router as nft_router
from api.payment import router as payment_router
from api.email import router as email_router
from models import *  # noqa: F401,F403 ensure model registration
from core.reconciliation import start_reconciliation_scheduler, shutdown_reconciliation_scheduler

logger = logging.getLogger(__name__)

# Required columns definition reused for legacy table repair
REQUIRED_NFT_COLUMNS = {
    'description': 'TEXT',
    'image_url': 'TEXT NOT NULL DEFAULT ""',
    'price_inr': 'DECIMAL(10,2) NOT NULL DEFAULT 0',
    'price_usd': 'DECIMAL(10,2) NOT NULL DEFAULT 0',
    'category': 'VARCHAR(100)',
    'is_sold': 'BOOLEAN NOT NULL DEFAULT FALSE',
    'is_reserved': 'BOOLEAN NOT NULL DEFAULT FALSE',
    'reserved_at': 'TIMESTAMPTZ',
    'sold_at': 'TIMESTAMPTZ',
    'owner_id': 'INTEGER',
    'created_at': 'TIMESTAMPTZ DEFAULT NOW()'
}

REQUIRED_USER_COLUMNS = {
    'name': 'VARCHAR(255) NOT NULL DEFAULT ""',
    'email': 'VARCHAR(255) NOT NULL',
    'google_id': 'VARCHAR(255) NOT NULL',
    'profile_pic': 'TEXT',
    'role': 'VARCHAR(50) NOT NULL DEFAULT "user"',
    'refresh_token': 'TEXT',
    'is_active': 'BOOLEAN NOT NULL DEFAULT TRUE',
    'created_at': 'TIMESTAMPTZ DEFAULT NOW()'
}

def ensure_nft_columns():
    """Ensure legacy/partial nfts table has all required columns (Postgres only)."""
    try:
        insp = inspect(engine)
        if 'nfts' not in insp.get_table_names():
            logger.info("nfts table not found yet; metadata create will handle it.")
            return
        existing = {c['name'] for c in insp.get_columns('nfts')}
        if all(col in existing for col in REQUIRED_NFT_COLUMNS):
            return
        with engine.begin() as conn:
            for col, ddl in REQUIRED_NFT_COLUMNS.items():
                if col not in existing:
                    logger.info(f"Adding missing column to nfts: {col}")
                    conn.execute(text(f'ALTER TABLE nfts ADD COLUMN {col} {ddl}'))
    except Exception as e:
        logger.warning(f"ensure_nft_columns failed: {e}")

def ensure_user_columns():
    """Ensure legacy/partial users table has all required columns (Postgres only)."""
    try:
        insp = inspect(engine)
        if 'users' not in insp.get_table_names():
            logger.info("users table not found yet; metadata create will handle it.")
            return
        existing = {c['name'] for c in insp.get_columns('users')}
        with engine.begin() as conn:
            for col, ddl in REQUIRED_USER_COLUMNS.items():
                if col not in existing:
                    logger.info(f"Adding missing column to users: {col}")
                    conn.execute(text(f'ALTER TABLE users ADD COLUMN {col} {ddl}'))
    except Exception as e:
        logger.warning(f"ensure_user_columns failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting NFT Marketplace API...")
    
    # Validate environment variables (non-fatal if missing optional ones)
    try:
        validate_env_variables()
    except Exception as e:
        logger.warning(f"Env validation warning: {e}")
    
    # Create database tables
    create_tables()
    logger.info("Database tables created/verified")

    # Repair legacy nfts table columns (mostly for Postgres migrations)
    ensure_nft_columns()
    ensure_user_columns()

    # Start reconciliation scheduler if enabled
    start_reconciliation_scheduler()
    
    # NOTE: Seeding moved to scripts/seed_nfts.py; keep runtime clean
    logger.info("Startup complete. Use 'python -m scripts.seed_nfts auto' to seed images.")
    
    yield
    
    # Shutdown
    shutdown_reconciliation_scheduler()
    logger.info("Shutting down NFT Marketplace API...")

# Create FastAPI app
app = FastAPI(
    title="NFT Marketplace API",
    description="A single-sale NFT marketplace with Google OAuth, INR/USD payments, and admin verification",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Mount local images (adjust directory if needed)
app.mount("/static", StaticFiles(directory="images"), name="static")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "data": None
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "data": None
        }
    )

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "NFT Marketplace API is running"}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "NFT Marketplace API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(nft_router, prefix="/api")
app.include_router(payment_router, prefix="/api")
app.include_router(email_router, prefix="/api")

# Backward-compatibility: also expose NFT routes at /nft/* (no /api prefix)
# This handles older frontend requests like `/nft/list?page=1&limit=50`.
app.include_router(nft_router)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Ensure securitySchemes
    components = openapi_schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT"
    }
    # Mark selected protected paths (those using JWT) with security requirement
    protected_prefixes = [
        "/api/auth/me", "/api/auth/profile", "/api/auth/logout", "/api/nft/{nft_id}/buy"
    ]
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, op in methods.items():
            if any(path.startswith(p.rstrip("{nft_id}/buy")) or path == p for p in protected_prefixes):
                # attach security requirement if not already
                op.setdefault("security", [{"BearerAuth": []}])
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi  # type: ignore

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
