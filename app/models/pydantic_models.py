from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

# Base response models
class BaseResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None

class PaginationInfo(BaseModel):
    total: int
    page: int
    size: int
    pages: int

# User models
class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    google_id: str
    profile_pic: Optional[str] = None

class UserResponse(UserBase):
    id: int
    role: str
    profile_pic: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# NFT models
class NFTBase(BaseModel):
    title: str
    image_url: str
    price_inr: Decimal
    price_usd: Decimal
    category: Optional[str] = None

class NFTCreate(NFTBase):
    pass

class NFTUpdate(BaseModel):
    title: Optional[str] = None
    image_url: Optional[str] = None
    price_inr: Optional[Decimal] = None
    price_usd: Optional[Decimal] = None
    category: Optional[str] = None

class NFTResponse(NFTBase):
    id: int
    is_sold: bool
    is_reserved: bool
    reserved_at: Optional[datetime] = None
    sold_to_user_id: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Transaction models
class TransactionCreate(BaseModel):
    nft_id: int
    payment_method: str
    buyer_currency: str

class TransactionResponse(BaseModel):
    id: int
    user_id: int
    nft_id: int
    payment_method: str
    status: str
    txn_ref: Optional[str] = None
    buyer_currency: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Purchase models
class INRPurchaseRequest(BaseModel):
    form_data: Dict[str, str]
    
    @field_validator('form_data')
    def validate_form_data(cls, v):
        required_fields = ['name', 'email', 'phone']
        for field in required_fields:
            if field not in v:
                raise ValueError(f'Missing required field: {field}')
        return v

class PayPalCreateRequest(BaseModel):
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None

# Admin models
class TransactionVerificationRequest(BaseModel):
    status: str
    
    @field_validator('status')
    def validate_status(cls, v):
        if v not in ['paid', 'failed']:
            raise ValueError('Status must be either "paid" or "failed"')
        return v

# Analytics models
class AnalyticsEvent(BaseModel):
    event_type: str
    nft_id: Optional[int] = None
    event_data: Optional[Dict[str, Any]] = None

class AnalyticsResponse(BaseModel):
    id: int
    nft_id: Optional[int] = None
    user_id: Optional[int] = None
    event_type: str
    event_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Token models
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefresh(BaseModel):
    refresh_token: str

# WebSocket models
class WebSocketMessage(BaseModel):
    event: str
    data: Dict[str, Any]
