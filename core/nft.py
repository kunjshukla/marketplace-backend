from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from models.nft import NFT
from models.transaction import Transaction

logger = logging.getLogger(__name__)

def reserve_nft(nft_id: int, user_id: int, db: Session) -> bool:
    """Reserve NFT for INR payment (15 minutes)"""
    try:
        nft = db.query(NFT).filter(NFT.id == nft_id).first()
        
        if not nft or nft.is_sold or nft.is_reserved:
            return False
        
        nft.is_reserved = True
        nft.reserved_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"NFT {nft_id} reserved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error reserving NFT: {e}")
        db.rollback()
        return False

def release_expired_reservations(db: Session):
    """Release NFT reservations that have expired (15 minutes)"""
    try:
        expiry_time = datetime.utcnow() - timedelta(minutes=15)
        
        expired_nfts = db.query(NFT).filter(
            NFT.is_reserved == True,
            NFT.reserved_at < expiry_time,
            NFT.is_sold == False
        ).all()
        
        for nft in expired_nfts:
            nft.is_reserved = False
            nft.reserved_at = None
            
            # Also cancel pending transactions for expired reservations
            pending_transactions = db.query(Transaction).filter(
                Transaction.nft_id == nft.id,
                Transaction.payment_status == "pending",
                Transaction.created_at < expiry_time
            ).all()
            
            for transaction in pending_transactions:
                transaction.payment_status = "expired"
        
        db.commit()
        
        if expired_nfts:
            logger.info(f"Released {len(expired_nfts)} expired NFT reservations")
        
    except Exception as e:
        logger.error(f"Error releasing expired reservations: {e}")
        db.rollback()

def mark_nft_sold(nft_id: int, user_id: int, db: Session) -> bool:
    """Mark NFT as sold to user"""
    try:
        nft = db.query(NFT).filter(NFT.id == nft_id).first()
        
        if not nft:
            return False
        
        nft.is_sold = True
        nft.is_reserved = False
        nft.owner_id = user_id
        nft.sold_at = datetime.utcnow()
        nft.reserved_at = None
        
        db.commit()
        
        logger.info(f"NFT {nft_id} marked as sold to user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error marking NFT as sold: {e}")
        db.rollback()
        return False
