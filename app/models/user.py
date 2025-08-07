from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, DECIMAL, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    google_id = Column(String(255), unique=True, nullable=False, index=True)
    profile_pic = Column(Text)
    role = Column(String(50), default="user")  # 'user' or 'admin'
    refresh_token = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user")
    purchased_nfts = relationship("NFT", back_populates="owner")
    analytics = relationship("Analytics", back_populates="user")
