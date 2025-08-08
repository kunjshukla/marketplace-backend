from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.base import Base

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nft_id = Column(Integer, ForeignKey("nfts.id"), nullable=False)
    payment_mode = Column(String(50), nullable=False)  # 'INR', 'USD', 'PAYPAL'
    payment_status = Column(String(50), default="pending", index=True)  # 'pending', 'completed', 'failed'
    txn_ref = Column(String(255), nullable=True)  # PayPal ID, UPI ref, or transaction reference
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(10), nullable=False)  # 'INR', 'USD'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    nft = relationship("NFT", back_populates="transactions")
