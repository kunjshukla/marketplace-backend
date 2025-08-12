from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging
from typing import Optional, Dict, Any
import requests
from urllib.parse import quote

from db.session import get_db, SessionLocal
from models.transaction import Transaction
from models.nft import NFT
from core.payment import process_paypal_payment, verify_paypal_webhook
from core.auth import get_current_user
from models.user import User
from config.settings import settings
from pydantic import BaseModel
from core.emailer import generate_upi_qr_code
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payment", tags=["payment"])

# In-memory store for captured order IDs to avoid duplicate form logs (ephemeral)
_captured_orders: set[str] = set()

# ---------------- New lightweight PayPal create/capture flow (no DB write required) ----------------
class PayPalCreateIn(BaseModel):
    nft_id: int
    amount: str
    currency: str = "USD"
    return_url: str
    cancel_url: str

class PayPalCaptureIn(BaseModel):
    orderID: str
    nft_id: int
    buyer_email: str
    buyer_name: str

# Diagnostics: confirm environment mode and client id prefix
logger.info("PayPal base: %s", settings.EFFECTIVE_PAYPAL_BASE)
cid = (settings.PAYPAL_CLIENT_ID or "")
logger.info("PayPal client id (prefix/len): %s*** (len=%d)", cid[:6], len(cid))

def _get_paypal_access_token() -> str:
    auth_url = f"{settings.EFFECTIVE_PAYPAL_BASE}/v1/oauth2/token"
    r = requests.post(auth_url, auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET), data={"grant_type": "client_credentials"}, timeout=10)
    if r.status_code != 200:

    # Extra diagnostics (no secrets)
        logger.error("PayPal token error details: status=%s, body=%s", r.status_code, r.text[:500])

        logger.error("PayPal token error: %s %s", r.status_code, r.text)
        raise HTTPException(502, "PayPal token error")
    return r.json().get("access_token")

def _paypal_create_order(amount: str, currency: str, return_url: str, cancel_url: str) -> Dict[str, Any]:
    token = _get_paypal_access_token()
    url = f"{settings.EFFECTIVE_PAYPAL_BASE}/v2/checkout/orders"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{"amount": {"currency_code": currency, "value": amount}}],
        "application_context": {"return_url": return_url, "cancel_url": cancel_url}
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code not in (200, 201):
        logger.error("PayPal create failed: %s %s", r.status_code, r.text)
        raise HTTPException(502, "PayPal create order failed")
    return r.json()

def _paypal_capture_order(order_id: str) -> Dict[str, Any]:
    token = _get_paypal_access_token()
    url = f"{settings.EFFECTIVE_PAYPAL_BASE}/v2/checkout/orders/{order_id}/capture"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    r = requests.post(url, headers=headers, timeout=15)
    if r.status_code not in (200, 201):
        logger.error("PayPal capture failed: %s %s", r.status_code, r.text)
        raise HTTPException(502, "PayPal capture failed")
    return r.json()

def _log_to_google_form(field_map: Dict[str, str]) -> bool:
    if not settings.GOOGLE_FORM_URL:
        return False
    try:
        r = requests.post(settings.GOOGLE_FORM_URL, data=field_map, timeout=6)
        return r.status_code in (200, 302)
    except Exception as e:
        logger.warning("Google Form logging failed: %s", e)
        return False

@router.post("/paypal/create", summary="Lightweight PayPal create order (stateless)")
async def paypal_create_order(data: PayPalCreateIn):
    order = _paypal_create_order(data.amount, data.currency, data.return_url, data.cancel_url)
    links = {l.get("rel"): l.get("href") for l in order.get("links", [])}
    return {"success": True, "order": order, "approve_url": links.get("approve")}

@router.post("/paypal/capture", summary="Lightweight PayPal capture order (logs to Google Form)")
async def paypal_capture_order(body: PayPalCaptureIn):
    if body.orderID in _captured_orders:
        return {"success": True, "duplicate": True}
    result = _paypal_capture_order(body.orderID)
    status_val = result.get("status")
    if status_val != "COMPLETED":
        logger.warning("Capture status not COMPLETED: %s", status_val)
        raise HTTPException(400, "Payment not completed")
    txn_id = None
    try:
        captures = result.get("purchase_units", [])[0].get("payments", {}).get("captures", [])
        if captures:
            txn_id = captures[0].get("id")
    except Exception:
        txn_id = None
    field_map = {}
    if all([settings.GF_ENTRY_NAME, settings.GF_ENTRY_EMAIL, settings.GF_ENTRY_NFT_ID, settings.GF_ENTRY_METHOD, settings.GF_ENTRY_TXN]):
        field_map = {
            settings.GF_ENTRY_NAME: body.buyer_name,
            settings.GF_ENTRY_EMAIL: body.buyer_email,
            settings.GF_ENTRY_NFT_ID: str(body.nft_id),
            settings.GF_ENTRY_METHOD: "PAYPAL",
            settings.GF_ENTRY_TXN: txn_id or body.orderID,
        }
    logged = _log_to_google_form(field_map) if field_map else False
    _captured_orders.add(body.orderID)
    return {"success": True, "txn_id": txn_id, "logged_to_form": logged, "raw": result}

# ---------------- Existing transaction-based endpoints below (unchanged) ----------------

@router.post("/paypal/create-legacy")
async def create_paypal_payment(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create PayPal payment (legacy transaction-based)."""
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
        if not verify_paypal_webhook(body, headers):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        webhook_data = await request.json()
        event_type = webhook_data.get("event_type")
        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            resource = webhook_data.get("resource", {})
            custom_id = resource.get("custom_id")
            if custom_id:
                transaction = db.query(Transaction).filter(Transaction.id == int(custom_id)).first()
                if transaction:
                    transaction.payment_status = "completed"
                    transaction.txn_ref = resource.get("id")
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

@router.get("/paypal/client-id", summary="Return public PayPal client ID for frontend SDK")
async def get_paypal_client_id():
    cid = settings.PAYPAL_CLIENT_ID or ""
    env = "live" if "api-m.paypal.com" in settings.EFFECTIVE_PAYPAL_BASE else "sandbox"
    return {"client_id": cid, "environment": env}

@router.get("/upi/qr/{transaction_id}", summary="Serve UPI QR code image for a transaction")
async def get_upi_qr(transaction_id: int):
    db = SessionLocal()
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    qr_path = generate_upi_qr_code(txn)
    if not qr_path or not qr_path.exists():
        raise HTTPException(404, "QR code not found")
    return FileResponse(str(qr_path), media_type="image/png")

@router.get("/upi/link/{transaction_id}", summary="Return UPI deep link for a transaction")
async def get_upi_link(transaction_id: int):
    db = SessionLocal()
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    payee_vpa = settings.UPI_ID
    payee_name = getattr(settings, 'UPI_PAYEE_NAME', None) or 'NFT Marketplace'
    tr_ref = str(txn.id)
    amount = txn.amount
    pn_enc = quote(payee_name, safe='')
    tn_enc = quote(f"NFT Purchase Transaction {txn.id}", safe='')
    upi_url = (
        f"upi://pay?pa={payee_vpa}"
        f"&pn={pn_enc}"
        f"&am={amount}"
        f"&cu=INR"
        f"&tr={tr_ref}"
        f"&tn={tn_enc}"
    )
    return {"success": True, "upi_link": upi_url}
