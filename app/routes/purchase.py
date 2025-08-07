from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import paypalrestsdk
import logging
import asyncio
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64

from app.db.session import get_db
from app.models.user import User
from app.models.nft import NFT
from app.models.transaction import Transaction
from app.models.analytics import Analytics
from app.models.pydantic_models import (
    INRPurchaseRequest, PayPalCreateRequest, TransactionResponse
)
from app.routes.auth import get_current_user
from app.utils.response import success_response, error_response
from app.utils.qr import generate_upi_qr
from app.utils.pdf import generate_ownership_certificate
from app.config import (
    PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_BASE_URL,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, UPI_ID
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/purchase", tags=["purchase"])

# Configure PayPal
paypalrestsdk.configure({
    "mode": "sandbox",  # Change to "live" for production
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_CLIENT_SECRET
})

async def send_email(to_email: str, subject: str, body: str, attachment_data: bytes = None, attachment_name: str = None):
    """Send email with optional attachment"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        if attachment_data and attachment_name:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment_data)
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment_name}'
            )
            msg.attach(part)
        
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_USER,
            password=SMTP_PASSWORD
        )
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

@router.post("/inr/{nft_id}")
async def purchase_nft_inr(
    nft_id: int,
    request: INRPurchaseRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate INR purchase with UPI QR code"""
    try:
        # Get NFT
        nft = db.query(NFT).filter(NFT.id == nft_id).first()
        if not nft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NFT not found"
            )
        
        # Check if NFT is available
        if nft.is_sold:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="NFT is already sold"
            )
        
        if nft.is_reserved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="NFT is currently reserved"
            )
        
        # Create transaction
        transaction = Transaction(
            user_id=current_user.id,
            nft_id=nft_id,
            payment_method="INR",
            status="pending",
            buyer_currency="INR"
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        # Reserve NFT for 24 hours
        nft.is_reserved = True
        nft.reserved_at = datetime.utcnow()
        db.commit()
        
        # Track analytics
        analytics_event = Analytics(
            user_id=current_user.id,
            nft_id=nft_id,
            event_type="purchase_inr_start",
            event_data={
                "transaction_id": transaction.id,
                "amount_inr": float(nft.price_inr),
                "form_data": request.form_data
            }
        )
        db.add(analytics_event)
        db.commit()
        
        # Generate UPI QR code
        try:
            qr_base64 = generate_upi_qr(
                amount=float(nft.price_inr),
                transaction_id=str(transaction.id),
                merchant_name="NFT Marketplace"
            )
            
            # Email QR code to user
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; color: white;">
                    <h1 style="margin: 0; font-size: 28px;">Payment Required</h1>
                    <p style="margin: 10px 0; font-size: 16px;">Complete your NFT purchase</p>
                </div>
                
                <div style="padding: 30px; background: #f9f9f9;">
                    <h2 style="color: #333; margin-bottom: 20px;">NFT Purchase Details</h2>
                    <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <p><strong>NFT:</strong> {nft.title}</p>
                        <p><strong>Price:</strong> ₹{nft.price_inr:,.2f}</p>
                        <p><strong>Transaction ID:</strong> {transaction.id}</p>
                        <p><strong>Buyer:</strong> {request.form_data.get('name', current_user.name)}</p>
                    </div>
                    
                    <h3 style="color: #333;">Payment Instructions</h3>
                    <ol style="color: #555; line-height: 1.6;">
                        <li>Open any UPI app (PhonePe, Google Pay, Paytm, etc.)</li>
                        <li>Scan the QR code below</li>
                        <li>Verify the amount: ₹{nft.price_inr:,.2f}</li>
                        <li>Complete the payment</li>
                        <li>Keep the UPI transaction ID for verification</li>
                    </ol>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <img src="data:image/png;base64,{qr_base64}" alt="UPI QR Code" style="max-width: 300px; border: 1px solid #ddd; border-radius: 8px;">
                    </div>
                    
                    <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0; color: #856404;"><strong>Important:</strong> This NFT is reserved for 24 hours. Please complete payment within this time to secure your purchase.</p>
                    </div>
                    
                    <div style="text-align: center; margin-top: 30px;">
                        <p style="color: #777;">Need help? Contact our support team.</p>
                    </div>
                </div>
                
                <div style="background: #333; color: white; text-align: center; padding: 20px;">
                    <p style="margin: 0;">© NFT Marketplace - Your Digital Art Destination</p>
                </div>
            </body>
            </html>
            """
            
            background_tasks.add_task(
                send_email,
                request.form_data.get('email', current_user.email),
                f"Payment Required - {nft.title}",
                email_body
            )
            
        except Exception as e:
            logger.error(f"Failed to generate/send QR code: {e}")
            # Don't fail the transaction, just log the error
        
        logger.info(f"INR purchase initiated for NFT {nft_id} by user {current_user.id}")
        
        return success_response(
            data={
                "transaction_id": transaction.id,
                "status": "reserved",
                "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
                "amount_inr": float(nft.price_inr)
            },
            message="NFT reserved successfully. Check your email for payment instructions."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating INR purchase: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate purchase"
        )

@router.post("/usd/{nft_id}")
async def purchase_nft_usd(
    nft_id: int,
    request: PayPalCreateRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate USD purchase with PayPal"""
    try:
        # Get NFT
        nft = db.query(NFT).filter(NFT.id == nft_id).first()
        if not nft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NFT not found"
            )
        
        # Check if NFT is available
        if nft.is_sold:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="NFT is already sold"
            )
        
        if nft.is_reserved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="NFT is currently reserved"
            )
        
        # Create transaction
        transaction = Transaction(
            user_id=current_user.id,
            nft_id=nft_id,
            payment_method="USD",
            status="pending",
            buyer_currency="USD"
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        # Track analytics
        analytics_event = Analytics(
            user_id=current_user.id,
            nft_id=nft_id,
            event_type="purchase_usd_start",
            event_data={
                "transaction_id": transaction.id,
                "amount_usd": float(nft.price_usd)
            }
        )
        db.add(analytics_event)
        db.commit()
        
        # Create PayPal payment
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"
            },
            "redirect_urls": {
                "return_url": request.return_url if request and request.return_url else "http://localhost:3000/purchase/success",
                "cancel_url": request.cancel_url if request and request.cancel_url else "http://localhost:3000/purchase/cancel"
            },
            "transactions": [{
                "item_list": {
                    "items": [{
                        "name": nft.title,
                        "sku": str(nft.id),
                        "price": str(nft.price_usd),
                        "currency": "USD",
                        "quantity": 1
                    }]
                },
                "amount": {
                    "total": str(nft.price_usd),
                    "currency": "USD"
                },
                "description": f"Purchase of NFT: {nft.title}",
                "custom": str(transaction.id)  # Store transaction ID
            }]
        })
        
        if payment.create():
            # Store PayPal payment ID
            transaction.txn_ref = payment.id
            db.commit()
            
            # Get approval URL
            approval_url = None
            for link in payment.links:
                if link.rel == "approval_url":
                    approval_url = link.href
                    break
            
            logger.info(f"PayPal payment created for NFT {nft_id} by user {current_user.id}")
            
            return success_response(
                data={
                    "transaction_id": transaction.id,
                    "paypal_payment_id": payment.id,
                    "approval_url": approval_url,
                    "amount_usd": float(nft.price_usd)
                },
                message="PayPal payment created successfully"
            )
        else:
            logger.error(f"PayPal payment creation failed: {payment.error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create PayPal payment"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating PayPal payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment"
        )

@router.post("/webhook/paypal")
async def paypal_webhook(
    request: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle PayPal webhook events"""
    try:
        logger.info(f"PayPal webhook received: {request.get('event_type')}")
        
        if request.get("event_type") == "PAYMENT.SALE.COMPLETED":
            # Extract transaction details
            sale = request["resource"]
            custom_field = sale.get("custom")
            
            if not custom_field:
                logger.warning("PayPal webhook missing custom field (transaction ID)")
                return success_response(message="Webhook processed")
            
            # Find transaction
            transaction = db.query(Transaction).filter(
                Transaction.id == int(custom_field),
                Transaction.payment_method == "USD",
                Transaction.status == "pending"
            ).first()
            
            if not transaction:
                logger.warning(f"Transaction not found for PayPal custom field: {custom_field}")
                return success_response(message="Transaction not found")
            
            # Get NFT and user
            nft = db.query(NFT).filter(NFT.id == transaction.nft_id).first()
            user = db.query(User).filter(User.id == transaction.user_id).first()
            
            if not nft or not user:
                logger.error(f"NFT or User not found for transaction {transaction.id}")
                return success_response(message="Invalid transaction data")
            
            # Update transaction and NFT
            transaction.status = "paid"
            transaction.txn_ref = sale.get("id", transaction.txn_ref)
            nft.is_sold = True
            nft.sold_to_user_id = user.id
            nft.is_reserved = False
            nft.reserved_at = None
            
            db.commit()
            
            # Track analytics
            analytics_event = Analytics(
                user_id=user.id,
                nft_id=nft.id,
                event_type="purchase_completed",
                event_data={
                    "transaction_id": transaction.id,
                    "payment_method": "USD",
                    "amount_usd": float(nft.price_usd),
                    "paypal_sale_id": sale.get("id")
                }
            )
            db.add(analytics_event)
            db.commit()
            
            # Generate and send PDF certificate
            background_tasks.add_task(
                send_ownership_certificate,
                transaction.id,
                user.email
            )
            
            logger.info(f"PayPal payment completed for transaction {transaction.id}")
        
        return success_response(message="Webhook processed successfully")
        
    except Exception as e:
        logger.error(f"PayPal webhook error: {e}")
        return success_response(message="Webhook processing failed")

async def send_ownership_certificate(transaction_id: int, user_email: str):
    """Generate and send PDF ownership certificate"""
    try:
        # This would typically use a database session
        # For now, we'll create a simple implementation
        logger.info(f"Generating ownership certificate for transaction {transaction_id}")
        
        # Generate PDF certificate (simplified)
        certificate_pdf = b"Dummy PDF certificate content"
        
        # Send email with certificate
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; color: white;">
                <h1 style="margin: 0; font-size: 28px;">🎉 Purchase Confirmed!</h1>
                <p style="margin: 10px 0; font-size: 16px;">Your NFT ownership certificate is ready</p>
            </div>
            
            <div style="padding: 30px; background: #f9f9f9;">
                <h2 style="color: #333;">Congratulations on your NFT purchase!</h2>
                <p style="color: #555; line-height: 1.6;">
                    Your payment has been confirmed and the NFT is now officially yours. 
                    Attached is your ownership certificate - please keep this safe as proof of ownership.
                </p>
                
                <div style="background: #d4edda; border: 1px solid #c3e6cb; border-radius: 8px; padding: 15px; margin: 20px 0;">
                    <p style="margin: 0; color: #155724;"><strong>What's next?</strong> Your NFT is now part of your collection and cannot be sold again by anyone else.</p>
                </div>
                
                <div style="text-align: center; margin-top: 30px;">
                    <p style="color: #777;">Thank you for choosing NFT Marketplace!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        await send_email(
            user_email,
            "NFT Ownership Certificate - Purchase Confirmed",
            email_body,
            certificate_pdf,
            f"nft_certificate_{transaction_id}.pdf"
        )
        
    except Exception as e:
        logger.error(f"Failed to send ownership certificate: {e}")
