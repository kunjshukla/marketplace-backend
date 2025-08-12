# NFT Marketplace Backend

A FastAPI-based backend for a single-sale NFT marketplace with Google OAuth authentication, INR/USD payments, and admin verification system.

## Features

- Google OAuth 2.0 authentication
- JWT-based session management
- Single-sale NFT management
- INR payments via UPI QR codes
- USD payments via PayPal
- Admin verification dashboard
- PDF ownership certificates
- Mixpanel analytics integration
- WebSocket notifications
- Rate limiting and security features

## Setup

1. Install Python 3.10 and create virtual environment:
```bash
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env` file

4. Initialize database:
```bash
sqlite3 dev.db < scripts/setup_db.sql
```

5. Run Redis:
```bash
docker run -d -p 6379:6379 redis
```

6. Run the application:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Documentation

Once running, visit:
- API docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## Testing

Run tests with:
```bash
pytest tests/
```

## Deployment

Deploy to Railway with the included Procfile and environment variables.

## UPI Automated Payment Reconciliation

This backend can automatically confirm UPI payments by periodically checking an external source and matching incoming credits to pending transactions.

Configure via environment variables in `.env`:

- RECON_ENABLED=true
- RECON_SOURCE=gmail_imap  # options: none | gmail_imap | dummy
- RECON_INTERVAL_SECONDS=120
- RECON_LOOKBACK_MINUTES=180
- IMAP_HOST=imap.gmail.com
- IMAP_PORT=993
- IMAP_USER=your.email@gmail.com
- IMAP_PASSWORD=your-app-password
- IMAP_FOLDER=INBOX
- UPI_ID=your-vpa@bank
- UPI_PAYEE_NAME=Your Name or Store

Notes:
- gmail_imap uses IMAP to scan recent emails for UPI credit alerts. Use an App Password if using Gmail with 2FA.
- dummy source marks all pending INR transactions as paid (for local testing only).
- When a match is found, the job sets transaction.payment_status to "completed", marks the NFT as sold, and emails a receipt to the buyer.

The scheduler starts automatically at app startup when RECON_ENABLED is true. It stops at shutdown.
