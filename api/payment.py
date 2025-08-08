from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging

from db.session import get_db
from models.transaction import Transaction
from models.nft import NFT
from core.payment import process_paypal_payment, verify_paypal_webhook
from core.auth import get_current_user
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payment", tags=["payment"])

@router.post("/paypal/create")
async def create_paypal_payment(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create PayPal payment"""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
        Transaction.payment_status == "pending"
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found or not eligible for payment"
        )
    
    try:
        payment_result = await process_paypal_payment(transaction)
        
        return {
            "success": True,
            "message": "PayPal payment created successfully",
            "data": payment_result
        }
        
    except Exception as e:
        logger.error(f"PayPal payment creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create PayPal payment"
        )

@router.post("/paypal/webhook")
async def paypal_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle PayPal webhook events"""
    try:
        body = await request.body()
        headers = dict(request.headers)
        
        # Verify webhook signature
        if not verify_paypal_webhook(body, headers):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        webhook_data = await request.json()
        event_type = webhook_data.get("event_type")
        
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            # Handle successful payment
            resource = webhook_data.get("resource", {})
            custom_id = resource.get("custom_id")  # This should be our transaction_id
            
            if custom_id:
                transaction = db.query(Transaction).filter(Transaction.id == int(custom_id)).first()
                if transaction:
                    transaction.payment_status = "completed"
                    transaction.txn_ref = resource.get("id")
                    
                    # Mark NFT as sold
                    nft = db.query(NFT).filter(NFT.id == transaction.nft_id).first()
                    if nft:
                        nft.is_sold = True
                        nft.owner_id = transaction.user_id
                        nft.sold_at = transaction.updated_at
                    
                    db.commit()
                    logger.info(f"PayPal payment completed for transaction {transaction.id}")
        
        return {"success": True, "message": "Webhook processed successfully"}
        
    except Exception as e:
        logger.error(f"PayPal webhook processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )

@router.post("/upi/confirm")
async def confirm_upi_payment(
    transaction_id: int,
    upi_ref: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm UPI payment (for admin verification)"""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id,
        Transaction.payment_status == "pending",
        Transaction.payment_mode == "INR"
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found or not eligible for confirmation"
        )
    
    # Update transaction with UPI reference
    transaction.txn_ref = upi_ref
    transaction.payment_status = "awaiting_verification"
    db.commit()
    
    return {
        "success": True,
        "message": "UPI payment reference submitted for verification",
        "data": {
            "transaction_id": transaction.id,
            "status": "awaiting_verification"
        }
    }
