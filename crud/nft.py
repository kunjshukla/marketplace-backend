from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from models.nft import NFT
from schemas.nft import NFTCreate, NFTUpdate

logger = logging.getLogger(__name__)

def get_nft_by_id(db: Session, nft_id: int) -> Optional[NFT]:
    """Get NFT by ID"""
    return db.query(NFT).filter(NFT.id == nft_id).first()

def get_available_nfts(db: Session, skip: int = 0, limit: int = 100, category: str = None) -> List[NFT]:
    """Get available NFTs (not sold)"""
    query = db.query(NFT).filter(NFT.is_sold == False)
    
    if category:
        query = query.filter(NFT.category == category)
    
    return query.offset(skip).limit(limit).all()

def get_nfts_by_owner(db: Session, owner_id: int) -> List[NFT]:
    """Get NFTs owned by user"""
    return db.query(NFT).filter(NFT.owner_id == owner_id).all()

def create_nft(db: Session, nft_data: NFTCreate) -> NFT:
    """Create new NFT"""
    try:
        db_nft = NFT(
            title=nft_data.title,
            description=nft_data.description,
            image_url=nft_data.image_url,
            price_inr=nft_data.price_inr,
            price_usd=nft_data.price_usd,
            category=nft_data.category
        )
        
        db.add(db_nft)
        db.commit()
        db.refresh(db_nft)
        
        logger.info(f"Created new NFT: {nft_data.title}")
        return db_nft
        
    except Exception as e:
        logger.error(f"Error creating NFT: {e}")
        db.rollback()
        raise e

def update_nft(db: Session, nft_id: int, nft_data: NFTUpdate) -> Optional[NFT]:
    """Update NFT"""
    try:
        nft = get_nft_by_id(db, nft_id)
        if not nft:
            return None
        
        update_data = nft_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(nft, field, value)
        
        db.commit()
        db.refresh(nft)
        
        logger.info(f"Updated NFT {nft_id}")
        return nft
        
    except Exception as e:
        logger.error(f"Error updating NFT: {e}")
        db.rollback()
        raise e

def reserve_nft(db: Session, nft_id: int) -> bool:
    """Reserve NFT for purchase"""
    try:
        nft = get_nft_by_id(db, nft_id)
        if not nft or nft.is_sold or nft.is_reserved:
            return False
        
        nft.is_reserved = True
        db.commit()
        
        logger.info(f"Reserved NFT {nft_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error reserving NFT: {e}")
        db.rollback()
        return False

def mark_nft_sold(db: Session, nft_id: int, owner_id: int) -> bool:
    """Mark NFT as sold"""
    try:
        nft = get_nft_by_id(db, nft_id)
        if not nft:
            return False
        
        nft.is_sold = True
        nft.is_reserved = False
        nft.owner_id = owner_id
        
        db.commit()
        
        logger.info(f"Marked NFT {nft_id} as sold to user {owner_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error marking NFT as sold: {e}")
        db.rollback()
        return False

def get_nft_count(db: Session, category: str = None, available_only: bool = True) -> int:
    """Get total NFT count"""
    query = db.query(NFT)
    
    if available_only:
        query = query.filter(NFT.is_sold == False)
    
    if category:
        query = query.filter(NFT.category == category)
    
    return query.count()
