from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.base import Base

class NFT(Base):
    __tablename__ = "nfts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=False)
    price_inr = Column(DECIMAL(10, 2), nullable=False)
    price_usd = Column(DECIMAL(10, 2), nullable=False)
    category = Column(String(100), nullable=True)  # e.g., 'art', 'collectible'
    is_sold = Column(Boolean, default=False, index=True)
    is_reserved = Column(Boolean, default=False, index=True)
    reserved_at = Column(DateTime(timezone=True), nullable=True)
    sold_at = Column(DateTime(timezone=True), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="purchased_nfts")
    transactions = relationship("Transaction", back_populates="nft")
