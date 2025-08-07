import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and responses"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        logger.info(f"Request: {request.method} {request.url.path} from {client_ip}")
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response (excluding sensitive endpoints)
        sensitive_paths = ["/auth/", "/admin/"]
        is_sensitive = any(path in str(request.url.path) for path in sensitive_paths)
        
        if not is_sensitive:
            logger.info(
                f"Response: {request.method} {request.url.path} "
                f"status={response.status_code} time={process_time:.4f}s"
            )
        else:
            logger.info(
                f"Response: {request.method} {request.url.path} "
                f"status={response.status_code} time={process_time:.4f}s [SENSITIVE]"
            )
        
        # Add response headers
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging errors"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(
                f"Error processing {request.method} {request.url.path}: {str(e)}",
                exc_info=True
            )
            # Re-raise the exception to be handled by FastAPI
            raise
