import imaplib
import email
import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from config.settings import settings
from db.session import SessionLocal
from models.transaction import Transaction
from models.nft import NFT
from models.user import User
from core.emailer import send_payment_receipt_email

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None

# -------- Helpers to fetch incoming UPI payments from sources --------

def _parse_amount(text: str) -> Optional[Decimal]:
    # Match amounts like 1,234.56 or 1234.56 with optional currency symbol
    m = re.search(r"(?:INR|Rs\.?|₹)\s*([0-9,]+(?:\.[0-9]{1,2})?)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"([0-9,]+(?:\.[0-9]{1,2})?)\s*(?:INR|Rs\.?|₹)", text, re.IGNORECASE)
    if not m:
        return None
    try:
        return Decimal(m.group(1).replace(",", ""))
    except InvalidOperation:
        return None

def _imap_fetch_recent_messages(since_dt: datetime) -> List[email.message.Message]:
    msgs: List[email.message.Message] = []
    if not settings.IMAP_USER or not settings.IMAP_PASSWORD:
        logger.warning("IMAP credentials not configured; cannot run reconciliation via gmail_imap")
        return msgs
    try:
        mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        mail.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        mail.select(settings.IMAP_FOLDER)
        # Search since date
        since_str = since_dt.strftime('%d-%b-%Y')
        typ, data = mail.search(None, '(SINCE "%s")' % since_str)
        if typ != 'OK':
            logger.warning("IMAP search failed: %s", typ)
            mail.logout()
            return msgs
        for num in data[0].split():
            typ, raw = mail.fetch(num, '(RFC822)')
            if typ != 'OK':
                continue
            msg = email.message_from_bytes(raw[0][1])
            msgs.append(msg)
        mail.logout()
    except Exception as e:
        logger.warning("IMAP fetch error: %s", e)
    return msgs

class IncomingPayment:
    def __init__(self, amount: Decimal, ref: str = "", note: str = "", when: Optional[datetime] = None):
        self.amount = amount
        self.ref = ref
        self.note = note
        self.when = when


def _extract_text_from_msg(msg: email.message.Message) -> str:
    parts: List[str] = []
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype in ("text/plain", "text/html"):
                    payload = part.get_payload(decode=True) or b""
                    parts.append(payload.decode(errors='ignore'))
        else:
            payload = msg.get_payload(decode=True) or b""
            parts.append(payload.decode(errors='ignore'))
    except Exception:
        pass
    return "\n".join(parts)


def _gmail_imap_list_payments(since_dt: datetime) -> List[IncomingPayment]:
    payments: List[IncomingPayment] = []
    msgs = _imap_fetch_recent_messages(since_dt)
    for msg in msgs:
        subj = msg.get('Subject', '')
        body = _extract_text_from_msg(msg)
        text = f"{subj}\n{body}"
        # Heuristic filters
        if settings.UPI_ID and settings.UPI_ID not in text:
            # Many bank alerts include payee VPA; if not present, still allow
            pass
        # Look for credit/received/UPI keywords
        if not re.search(r"UPI|credited|received|payment", text, re.IGNORECASE):
            continue
        amount = _parse_amount(text)
        if not amount:
            continue
        # Extract UPI reference like UPI Ref No 1234567890 or UTR/Ref
        mref = re.search(r"(?:UPI\s*(?:Ref(?:erence)?\s*No\.?|Txn\s*ID|UTR)\s*[:#-]?\s*)([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        ref = mref.group(1).strip() if mref else ""
        payments.append(IncomingPayment(amount=amount, ref=ref, note=text[:500]))
    return payments


def _dummy_list_payments(pending: List[Transaction]) -> List[IncomingPayment]:
    # For development: pretend all pending are paid
    return [IncomingPayment(amount=Decimal(tx.amount), ref=f"DUMMY-{tx.id}", note=f"Auto dummy match for tx {tx.id}") for tx in pending]


# -------- Core reconciliation job --------

def _match_and_complete(db: Session, txn: Transaction, payments: List[IncomingPayment]) -> bool:
    # Match by exact amount and presence of tx id in note or ref
    tid = str(txn.id)
    for p in payments:
        if Decimal(txn.amount) == Decimal(p.amount):
            text_blob = (p.ref or "") + "\n" + (p.note or "")
            if tid in text_blob:
                # Complete
                txn.payment_status = "completed"
                txn.txn_ref = p.ref or txn.txn_ref
                nft = db.query(NFT).filter(NFT.id == txn.nft_id).first()
                if nft:
                    nft.is_sold = True
                    nft.owner_id = txn.user_id
                    nft.sold_at = datetime.now(timezone.utc)
                db.commit()
                # Email receipt
                try:
                    user = db.query(User).filter(User.id == txn.user_id).first()
                    if user and user.email:
                        send_payment_receipt_email(user.email, user.name or "Buyer", txn)
                except Exception as e:
                    logger.warning("Failed to send receipt email for tx %s: %s", txn.id, e)
                logger.info("Reconciliation completed tx %s via auto-match", txn.id)
                return True
    return False


def reconciliation_tick():
    if settings.RECON_SOURCE == "none":
        return
    db = SessionLocal()
    try:
        lookback = datetime.now(timezone.utc) - timedelta(minutes=settings.RECON_LOOKBACK_MINUTES)
        pending = (
            db.query(Transaction)
            .filter(Transaction.payment_mode == "INR")
            .filter(Transaction.payment_status.in_(["pending", "awaiting_verification"]))
            .filter(Transaction.created_at >= lookback)
            .all()
        )
        if not pending:
            return
        if settings.RECON_SOURCE == "gmail_imap":
            incoming = _gmail_imap_list_payments(lookback)
        elif settings.RECON_SOURCE == "dummy":
            incoming = _dummy_list_payments(pending)
        else:
            incoming = []
        for txn in pending:
            try:
                _match_and_complete(db, txn, incoming)
            except Exception as e:
                logger.warning("Recon error for tx %s: %s", txn.id, e)
    except Exception as e:
        logger.warning("Reconciliation tick failed: %s", e)
    finally:
        db.close()


def start_reconciliation_scheduler() -> Optional[BackgroundScheduler]:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    if not settings.RECON_ENABLED:
        logger.info("Reconciliation disabled")
        return None
    try:
        sched = BackgroundScheduler(timezone=str(timezone.utc))
        sched.add_job(reconciliation_tick, 'interval', seconds=settings.RECON_INTERVAL_SECONDS, id='upi-recon', max_instances=1, coalesce=True)
        sched.start()
        _scheduler = sched
        logger.info("UPI reconciliation scheduler started: every %ss source=%s", settings.RECON_INTERVAL_SECONDS, settings.RECON_SOURCE)
        return sched
    except Exception as e:
        logger.warning("Failed to start reconciliation scheduler: %s", e)
        return None


def shutdown_reconciliation_scheduler():
    global _scheduler
    try:
        if _scheduler:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            logger.info("Reconciliation scheduler stopped")
    except Exception as e:
        logger.warning("Error stopping scheduler: %s", e)
