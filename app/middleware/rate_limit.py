import redis
import time
import json
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import REDIS_URL, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW
import logging

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = RATE_LIMIT_REQUESTS):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = RATE_LIMIT_WINDOW  # seconds
        
        try:
            self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis for rate limiting")
        except Exception as e:
            logger.warning(f"Could not connect to Redis: {e}. Rate limiting disabled.")
            self.redis_client = None
    
    async def dispatch(self, request: Request, call_next):
        if not self.redis_client:
            # If Redis is not available, skip rate limiting
            return await call_next(request)
        
        # Skip rate limiting for health checks and static files
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Get client identifier (IP address)
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"
        
        try:
            # Get current request count
            current_requests = self.redis_client.get(key)
            
            if current_requests is None:
                # First request from this IP
                self.redis_client.setex(key, self.window_size, 1)
                logger.debug(f"Rate limit initialized for {client_ip}")
            else:
                current_requests = int(current_requests)
                
                if current_requests >= self.requests_per_minute:
                    logger.warning(f"Rate limit exceeded for {client_ip}")
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "Rate limit exceeded",
                            "message": f"Maximum {self.requests_per_minute} requests per {self.window_size} seconds allowed",
                            "retry_after": self.redis_client.ttl(key)
                        }
                    )
                
                # Increment request count
                self.redis_client.incr(key)
                logger.debug(f"Rate limit count: {current_requests + 1}/{self.requests_per_minute} for {client_ip}")
            
            # Process the request
            response = await call_next(request)
            
            # Add rate limit headers
            remaining = max(0, self.requests_per_minute - int(self.redis_client.get(key) or 0))
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.redis_client.ttl(key))
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # If rate limiting fails, allow the request to proceed
            return await call_next(request)
