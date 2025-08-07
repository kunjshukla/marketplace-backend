from typing import Any, Dict, Optional
from pydantic import BaseModel

class APIResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None

def success_response(data: Any = None, message: str = None) -> Dict:
    """Create a success response"""
    return APIResponse(
        success=True,
        data=data,
        message=message
    ).model_dump()

def error_response(message: str, data: Any = None) -> Dict:
    """Create an error response"""
    return APIResponse(
        success=False,
        message=message,
        data=data
    ).model_dump()
