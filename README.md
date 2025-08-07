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
