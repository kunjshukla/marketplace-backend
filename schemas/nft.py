from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class NFTBase(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: str
    price_inr: Decimal
    price_usd: Decimal
    category: Optional[str] = None

class NFTCreate(NFTBase):
    pass

class NFTUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price_inr: Optional[Decimal] = None
    price_usd: Optional[Decimal] = None
    category: Optional[str] = None

class NFTResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    image_url: str
    price_inr: Decimal
    price_usd: Decimal
    category: Optional[str]
    is_sold: bool
    is_reserved: bool
    reserved_at: Optional[datetime]
    sold_at: Optional[datetime]
    owner_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True

class NFTListResponse(BaseModel):
    success: bool
    message: str
    data: dict  # Contains nfts, total, skip, limit

# NEW: detail response envelope for /nft/{id}
class NFTDetailResponse(BaseModel):
    success: bool
    message: str
    data: NFTResponse
