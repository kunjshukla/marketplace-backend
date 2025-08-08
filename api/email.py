from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict
import logging

from db.session import get_db
from core.emailer import send_upi_qr_email
from core.auth import get_current_user
from models.user import User
from models.transaction import Transaction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/email", tags=["email"])

@router.post("/send-qr")
async def send_upi_qr(
    transaction_id: int,
    buyer_details: Dict[str, str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send UPI QR code via email for INR payments"""
    
    # Verify transaction belongs to current user and is INR payment
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
        Transaction.payment_mode == "INR",
        Transaction.payment_status == "pending"
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found or not eligible for UPI payment"
        )
    
    try:
        # Send UPI QR email
        email_sent = await send_upi_qr_email(
            user_email=current_user.email,
            user_name=current_user.name,
            transaction=transaction,
            buyer_details=buyer_details
        )
        
        if not email_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email"
            )
        
        return {
            "success": True,
            "message": "UPI QR code sent to your email successfully",
            "data": {
                "transaction_id": transaction_id,
                "email_sent_to": current_user.email
            }
        }
        
    except Exception as e:
        logger.error(f"Error sending UPI QR email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send UPI QR email"
        )
