from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nft_id = Column(Integer, ForeignKey("nfts.id"), nullable=False)
    payment_method = Column(String(50), nullable=False)  # 'INR', 'USD', 'CRYPTO'
    status = Column(String(50), nullable=False, index=True)  # 'pending', 'paid', 'failed'
    txn_ref = Column(String(255))  # PayPal ID, UPI ref, or tx hash
    buyer_currency = Column(String(50), nullable=False)  # 'INR', 'USD', 'EUR'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    nft = relationship("NFT", back_populates="transactions")
