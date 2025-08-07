from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base

class Analytics(Base):
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    nft_id = Column(Integer, ForeignKey("nfts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String(50), index=True)  # 'view', 'purchase', 'click'
    event_data = Column(JSON)  # Metadata (e.g., browser, timestamp)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    nft = relationship("NFT", back_populates="analytics")
    user = relationship("User", back_populates="analytics")
