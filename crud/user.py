from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from models.user import User
from schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()

def get_user_by_google_id(db: Session, google_id: str) -> Optional[User]:
    """Get user by Google ID"""
    return db.query(User).filter(User.google_id == google_id).first()

def create_user(db: Session, user_data: UserCreate) -> User:
    """Create new user"""
    try:
        db_user = User(
            name=user_data.name,
            email=user_data.email,
            google_id=user_data.google_id,
            profile_pic=user_data.profile_pic
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"Created new user: {user_data.email}")
        return db_user
        
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        db.rollback()
        raise e

def update_user(db: Session, user_id: int, user_data: UserUpdate) -> Optional[User]:
    """Update user"""
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return None
        
        update_data = user_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        db.commit()
        db.refresh(user)
        
        logger.info(f"Updated user {user_id}")
        return user
        
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        db.rollback()
        raise e

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Get users with pagination"""
    return db.query(User).offset(skip).limit(limit).all()

def delete_user(db: Session, user_id: int) -> bool:
    """Soft delete user by setting is_active to False"""
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            return False
        
        user.is_active = False
        db.commit()
        
        logger.info(f"Deactivated user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error deactivating user: {e}")
        db.rollback()
        return False
