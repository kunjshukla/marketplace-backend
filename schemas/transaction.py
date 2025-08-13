from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class TransactionBase(BaseModel):
    user_id: int
    nft_id: int
    payment_mode: str  # 'INR', 'USD', 'PAYPAL'
    amount: Decimal
    currency: str  # 'INR', 'USD'

class TransactionCreate(TransactionBase):
    pass

class TransactionUpdate(BaseModel):
    payment_status: Optional[str] = None
    txn_ref: Optional[str] = None

class TransactionResponse(BaseModel):
    id: int
    user_id: int
    nft_id: int
    payment_mode: str
    payment_status: str
    txn_ref: Optional[str]
    amount: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
