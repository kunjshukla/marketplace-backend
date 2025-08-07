from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.config import BASE_DIR
from app.db.session import create_tables
from app.utils.validate_env import validate_env_variables
from app.middleware.logging import LoggingMiddleware, ErrorLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.utils.response import error_response

# Import routes
from app.routes.auth import router as auth_router
from app.routes.nft import router as nft_router
from app.routes.purchase import router as purchase_router
from app.routes.admin import router as admin_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting NFT Marketplace API...")
    
    # Validate environment variables
    validate_env_variables()
    
    # Create database tables
    create_tables()
    logger.info("Database tables created/verified")
    
    yield
    
    # Shutdown
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://vercel.app", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(ErrorLoggingMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        )
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=error_response(
            message="Internal server error"
        )
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
app.include_router(auth_router)
app.include_router(nft_router)
app.include_router(purchase_router)
app.include_router(admin_router)

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
