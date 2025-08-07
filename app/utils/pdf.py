from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
import base64
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def generate_ownership_certificate(
    nft_title: str,
    nft_image_url: str,
    buyer_name: str,
    buyer_email: str,
    transaction_id: str,
    purchase_date: datetime,
    amount: float,
    currency: str
) -> bytes:
    """Generate PDF ownership certificate"""
    try:
        # Create a bytes buffer
        buffer = io.BytesIO()
        
        # Create the PDF document
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=18,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=colors.darkgreen
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=12,
            alignment=TA_LEFT
        )
        
        # Title
        story.append(Paragraph("NFT OWNERSHIP CERTIFICATE", title_style))
        story.append(Spacer(1, 12))
        
        # Certificate content
        story.append(Paragraph("CERTIFICATE OF AUTHENTICITY", subtitle_style))
        story.append(Spacer(1, 20))
        
        # Certificate details
        cert_text = f"""
        This certificate confirms the authentic ownership of the following Non-Fungible Token (NFT):
        """
        story.append(Paragraph(cert_text, normal_style))
        story.append(Spacer(1, 12))
        
        # NFT Details Table
        nft_data = [
            ['NFT Title:', nft_title],
            ['Owner:', buyer_name],
            ['Email:', buyer_email],
            ['Purchase Date:', purchase_date.strftime('%B %d, %Y')],
            ['Transaction ID:', transaction_id],
            ['Purchase Amount:', f"{currency} {amount:.2f}"]
        ]
        
        nft_table = Table(nft_data, colWidths=[2*inch, 4*inch])
        nft_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(nft_table)
        story.append(Spacer(1, 30))
        
        # Authentication text
        auth_text = f"""
        This certificate serves as proof of ownership and authenticity of the above NFT. 
        The purchase was completed on our verified marketplace platform.
        
        Certificate generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')}
        """
        story.append(Paragraph(auth_text, normal_style))
        story.append(Spacer(1, 30))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.grey
        )
        
        footer_text = "NFT Marketplace - Digital Art Authentication Platform"
        story.append(Paragraph(footer_text, footer_style))
        
        # Build PDF
        doc.build(story)
        
        # Get the value of the BytesIO buffer and return it
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        logger.info(f"Generated PDF certificate for transaction {transaction_id}")
        return pdf_bytes
        
    except Exception as e:
        logger.error(f"Error generating PDF certificate: {e}")
        raise

def save_certificate(pdf_bytes: bytes, file_path: str) -> bool:
    """Save PDF certificate to file"""
    try:
        with open(file_path, 'wb') as f:
            f.write(pdf_bytes)
        return True
    except Exception as e:
        logger.error(f"Error saving PDF certificate: {e}")
        return False
