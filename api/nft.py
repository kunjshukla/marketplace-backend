from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from db.session import get_db
from models.nft import NFT
from models.transaction import Transaction
from schemas.nft import NFTResponse, NFTListResponse
from core.auth import get_current_user
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nft", tags=["nft"])

@router.get("/list", response_model=NFTListResponse)
async def list_nfts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List available NFTs"""
    try:
        query = db.query(NFT).filter(NFT.is_sold == False)
        
        if category:
            query = query.filter(NFT.category == category)
        
        total = query.count()
        nfts = query.offset(skip).limit(limit).all()
        
        # Normalize Decimal to float for safer JSON serialization
        serialized = []
        for n in nfts:
            serialized.append({
                "id": n.id,
                "title": n.title,
                "description": n.description,
                "image_url": n.image_url,
                "price_inr": float(n.price_inr) if n.price_inr is not None else None,
                "price_usd": float(n.price_usd) if n.price_usd is not None else None,
                "category": n.category,
                "is_sold": n.is_sold,
                "is_reserved": n.is_reserved,
                "reserved_at": n.reserved_at,
                "sold_at": n.sold_at,
                "owner_id": n.owner_id,
                "created_at": n.created_at
            })
        
        return {
            "success": True,
            "message": "NFTs retrieved successfully",
            "data": {
                "nfts": serialized,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing NFTs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve NFTs"
        )

@router.get("/{nft_id}", response_model=NFTResponse)
async def get_nft(nft_id: int, db: Session = Depends(get_db)):
    """Get specific NFT details"""
    nft = db.query(NFT).filter(NFT.id == nft_id).first()
    
    if not nft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NFT not found"
        )
    
    return {
        "success": True,
        "message": "NFT retrieved successfully",
        "data": nft
    }

@router.post("/{nft_id}/buy")
async def buy_nft(
    nft_id: int,
    payment_mode: str,  # 'INR' or 'USD'
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate NFT purchase"""
    nft = db.query(NFT).filter(NFT.id == nft_id).first()
    
    if not nft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NFT not found"
        )
    
    if nft.is_sold:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NFT is already sold"
        )
    
    if nft.is_reserved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NFT is currently reserved"
        )
    
    # Determine amount based on payment mode
    if payment_mode == "INR":
        amount = nft.price_inr
        currency = "INR"
    elif payment_mode == "USD":
        amount = nft.price_usd
        currency = "USD"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment mode. Use 'INR' or 'USD'"
        )
    
    # Create transaction
    transaction = Transaction(
        user_id=current_user.id,
        nft_id=nft_id,
        payment_mode=payment_mode,
        amount=amount,
        currency=currency,
        payment_status="pending"
    )
    
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    # Reserve NFT for INR payments
    if payment_mode == "INR":
        nft.is_reserved = True
        nft.reserved_at = transaction.created_at
        db.commit()
    
    return {
        "success": True,
        "message": "Purchase initiated successfully",
        "data": {
            "transaction_id": transaction.id,
            "payment_mode": payment_mode,
            "amount": float(amount),
            "currency": currency,
            "next_step": "complete_payment" if payment_mode == "USD" else "await_payment_confirmation"
        }
    }
