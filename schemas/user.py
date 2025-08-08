from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    google_id: str
    profile_pic: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    profile_pic: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    google_id: str
    profile_pic: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        orm_mode = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenRefresh(BaseModel):
    refresh_token: str
