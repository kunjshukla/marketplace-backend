import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

def create_smtp_client():
    """Create SMTP client for sending emails"""
    try:
        smtp_client = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        smtp_client.starttls()
        smtp_client.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        return smtp_client
        
    except Exception as e:
        logger.error(f"Error creating SMTP client: {e}")
        raise e

def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    from_email: str = None
):
    """Send HTML email"""
    try:
        if not from_email:
            from_email = settings.SMTP_USER
        
        msg = MIMEMultipart('alternative')
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email
        smtp_client = create_smtp_client()
        smtp_client.send_message(msg)
        smtp_client.quit()
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False
