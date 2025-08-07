import pyqrcode
import io
import base64
from typing import BinaryIO
from app.config import UPI_ID
import logging

logger = logging.getLogger(__name__)

def generate_upi_qr(amount: float, transaction_id: str, merchant_name: str = "NFT Marketplace") -> str:
    """Generate UPI QR code for payment"""
    try:
        if not UPI_ID:
            raise ValueError("UPI_ID not configured")
        
        # UPI payment string format
        upi_string = (
            f"upi://pay?"
            f"pa={UPI_ID}&"
            f"pn={merchant_name}&"
            f"am={amount:.2f}&"
            f"cu=INR&"
            f"tn=NFT Purchase {transaction_id}"
        )
        
        # Generate QR code
        qr = pyqrcode.create(upi_string)
        
        # Convert to PNG bytes
        buffer = io.BytesIO()
        qr.png(buffer, scale=8)
        buffer.seek(0)
        
        # Convert to base64 for embedding in emails
        qr_base64 = base64.b64encode(buffer.read()).decode()
        
        logger.info(f"Generated UPI QR code for transaction {transaction_id}")
        return qr_base64
        
    except Exception as e:
        logger.error(f"Error generating UPI QR code: {e}")
        raise

def save_qr_code(qr_base64: str, file_path: str) -> bool:
    """Save QR code to file"""
    try:
        qr_bytes = base64.b64decode(qr_base64)
        with open(file_path, 'wb') as f:
            f.write(qr_bytes)
        return True
    except Exception as e:
        logger.error(f"Error saving QR code: {e}")
        return False
