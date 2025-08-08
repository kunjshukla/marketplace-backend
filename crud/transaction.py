from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from models.transaction import Transaction
from schemas.transaction import TransactionCreate, TransactionUpdate

logger = logging.getLogger(__name__)

def get_transaction_by_id(db: Session, transaction_id: int) -> Optional[Transaction]:
    """Get transaction by ID"""
    return db.query(Transaction).filter(Transaction.id == transaction_id).first()

def get_transactions_by_user(db: Session, user_id: int) -> List[Transaction]:
    """Get transactions by user ID"""
    return db.query(Transaction).filter(Transaction.user_id == user_id).all()

def get_transaction_by_user_and_nft(db: Session, user_id: int, nft_id: int) -> Optional[Transaction]:
    """Get transaction by user and NFT"""
    return db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.nft_id == nft_id
    ).first()

def create_transaction(db: Session, transaction_data: TransactionCreate) -> Transaction:
    """Create new transaction"""
    try:
        db_transaction = Transaction(
            user_id=transaction_data.user_id,
            nft_id=transaction_data.nft_id,
            payment_mode=transaction_data.payment_mode,
            amount=transaction_data.amount,
            currency=transaction_data.currency,
            payment_status="pending"
        )
        
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        
        logger.info(f"Created new transaction: {db_transaction.id}")
        return db_transaction
        
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        db.rollback()
        raise e

def update_transaction(db: Session, transaction_id: int, transaction_data: TransactionUpdate) -> Optional[Transaction]:
    """Update transaction"""
    try:
        transaction = get_transaction_by_id(db, transaction_id)
        if not transaction:
            return None
        
        update_data = transaction_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(transaction, field, value)
        
        db.commit()
        db.refresh(transaction)
        
        logger.info(f"Updated transaction {transaction_id}")
        return transaction
        
    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
        db.rollback()
        raise e

def get_pending_transactions(db: Session) -> List[Transaction]:
    """Get pending transactions"""
    return db.query(Transaction).filter(Transaction.payment_status == "pending").all()

def get_transactions_by_status(db: Session, status: str) -> List[Transaction]:
    """Get transactions by status"""
    return db.query(Transaction).filter(Transaction.payment_status == status).all()

def complete_transaction(db: Session, transaction_id: int, txn_ref: str = None) -> bool:
    """Mark transaction as completed"""
    try:
        transaction = get_transaction_by_id(db, transaction_id)
        if not transaction:
            return False
        
        transaction.payment_status = "completed"
        if txn_ref:
            transaction.txn_ref = txn_ref
        
        db.commit()
        
        logger.info(f"Completed transaction {transaction_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error completing transaction: {e}")
        db.rollback()
        return False

def fail_transaction(db: Session, transaction_id: int, reason: str = None) -> bool:
    """Mark transaction as failed"""
    try:
        transaction = get_transaction_by_id(db, transaction_id)
        if not transaction:
            return False
        
        transaction.payment_status = "failed"
        
        db.commit()
        
        logger.info(f"Failed transaction {transaction_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error failing transaction: {e}")
        db.rollback()
        return False
