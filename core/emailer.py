import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
import logging
from typing import Dict
from urllib.parse import quote

from config.settings import settings
from models.transaction import Transaction
from utilities.smtp import create_smtp_client

logger = logging.getLogger(__name__)

async def send_upi_qr_email(
    user_email: str,
    user_name: str,
    transaction: Transaction,
    buyer_details: Dict[str, str]
) -> bool:
    """Send UPI QR code email for INR payments"""
    
    try:
        # Create email message
        msg = MIMEMultipart('related')
        msg['From'] = settings.SMTP_USER
        msg['To'] = user_email
        msg['Subject'] = f"UPI Payment for NFT Purchase - Transaction #{transaction.id}"
        
        # Load email template
        template_path = Path(__file__).parent.parent / "emails" / "upi_qr_template.html"
        
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        else:
            # Fallback HTML content
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h2 style="color: #333; text-align: center; margin-bottom: 30px;">NFT Purchase - UPI Payment</h2>
                        
                        <p>Dear {user_name},</p>
                        
                        <p>Thank you for your NFT purchase! Please complete your payment using the UPI QR code below:</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <img src="cid:upi_qr" alt="UPI QR Code" style="max-width: 300px; border: 2px solid #ddd; padding: 10px; border-radius: 8px;">
                        </div>
                        
                        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3 style="color: #333; margin-top: 0;">Payment Details:</h3>
                            <p><strong>Transaction ID:</strong> {transaction.id}</p>
                            <p><strong>Amount:</strong> ₹{transaction.amount}</p>
                            <p><strong>UPI ID:</strong> {settings.UPI_ID}</p>
                        </div>
                        
                        <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                            <h4 style="color: #856404; margin-top: 0;">Important Instructions:</h4>
                            <ul style="color: #856404; margin: 0; padding-left: 20px;">
                                <li>Scan the QR code using any UPI app (GPay, PhonePe, Paytm, etc.)</li>
                                <li>Enter the exact amount: ₹{transaction.amount}</li>
                                <li>Complete the payment within 15 minutes</li>
                                <li>After payment, note down the UPI transaction reference ID</li>
                                <li>Return to our website and submit the transaction reference for verification</li>
                            </ul>
                        </div>
                        
                        <p style="color: #666; font-size: 14px; text-align: center; margin-top: 30px;">
                            If you face any issues, please contact our support team.<br>
                            This is an automated email, please do not reply.
                        </p>
                    </div>
                </body>
            </html>
            """
        
        # Replace placeholders in template
        html_content = html_content.format(
            user_name=user_name,
            transaction_id=transaction.id,
            amount=transaction.amount,
            upi_id=settings.UPI_ID
        )
        
        # Attach HTML content
        msg.attach(MIMEText(html_content, 'html'))
        
        # Generate and attach UPI QR code
        qr_image_path = generate_upi_qr_code(transaction)
        if qr_image_path and qr_image_path.exists():
            with open(qr_image_path, 'rb') as f:
                qr_image = MIMEImage(f.read())
                qr_image.add_header('Content-ID', '<upi_qr>')
                msg.attach(qr_image)
        
        # Send email
        smtp_client = create_smtp_client()
        smtp_client.send_message(msg)
        smtp_client.quit()
        
        logger.info(f"UPI QR email sent successfully to {user_email} for transaction {transaction.id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending UPI QR email: {e}")
        return False

def generate_upi_qr_code(transaction: Transaction) -> Path:
    """Generate UPI QR code image"""
    try:
        import qrcode
        from PIL import Image
        
        # Compute standard UPI parameters
        payee_vpa = settings.UPI_ID
        payee_name = getattr(settings, 'UPI_PAYEE_NAME', None) or 'NFT Marketplace'
        amount = transaction.amount
        currency = 'INR'
        # Use transaction.id as unique reference for this QR
        tr_ref = str(transaction.id)
        # Optional note
        note = f"NFT Purchase Transaction {transaction.id}"
        
        # Percent-encode only fields that commonly contain spaces/special chars
        pn_enc = quote(payee_name, safe='')
        tn_enc = quote(note, safe='')
        
        # UPI payment URL per NPCI spec (common fields)
        upi_url = (
            f"upi://pay?pa={payee_vpa}"
            f"&pn={pn_enc}"
            f"&am={amount}"
            f"&cu={currency}"
            f"&tr={tr_ref}"
            f"&tn={tn_enc}"
        )
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(upi_url)
        qr.make(fit=True)
        
        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code
        qr_dir = Path(__file__).parent.parent / "images" / "upi_qr"
        qr_dir.mkdir(parents=True, exist_ok=True)
        
        qr_path = qr_dir / f"transaction_{transaction.id}.png"
        qr_image.save(qr_path)
        
        return qr_path
        
    except Exception as e:
        logger.error(f"Error generating UPI QR code: {e}")
        return None

# New: send simple payment receipt after automated reconciliation

def send_payment_receipt_email(user_email: str, user_name: str, transaction: Transaction) -> bool:
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = settings.SMTP_USER
        msg['To'] = user_email
        msg['Subject'] = f"Payment confirmed - Transaction #{transaction.id}"
        body = f"""
        <html>
        <body>
        <p>Hi {user_name},</p>
        <p>Your payment for transaction <strong>#{transaction.id}</strong> has been confirmed.</p>
        <p>Amount: ₹{transaction.amount}<br>
        Reference: {transaction.txn_ref or 'N/A'}</p>
        <p>Thank you for your purchase.</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        smtp = create_smtp_client()
        smtp.send_message(msg)
        smtp.quit()
        logger.info("Sent payment receipt email to %s for tx %s", user_email, transaction.id)
        return True
    except Exception as e:
        logger.warning("Failed to send payment receipt: %s", e)
        return False
