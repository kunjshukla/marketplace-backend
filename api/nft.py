from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from db.session import get_db
from models.nft import NFT
from models.transaction import Transaction
from schemas.nft import NFTResponse, NFTListResponse
from core.auth import get_current_user
from models.user import User

# NEW: Supabase client helper
from utilities.supabase_client import get_supabase

# NEW: typed response for detail endpoint
from schemas.nft import NFTDetailResponse
# NEW: body model for buy endpoint
from pydantic import BaseModel

class BuyRequest(BaseModel):
    payment_mode: str | None = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nft", tags=["nft"])

@router.get("/list", response_model=NFTListResponse)
async def list_nfts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List available NFTs. Prefer Supabase source if configured, else fallback to local DB."""
    try:
        # Try Supabase first
        sb = get_supabase()
        if sb is not None:
            query = sb.table("nfts").select("*").eq("is_sold", False)
            if category:
                query = query.eq("category", category)
            query = query.range(skip, skip + limit - 1)
            sb_resp = query.execute()
            nfts = sb_resp.data or []

            # total count (separate count query)
            count_q = sb.table("nfts").select("id", count="exact").eq("is_sold", False)
            if category:
                count_q = count_q.eq("category", category)
            total = getattr(count_q.execute(), "count", None)
            if total is None:
                total = len(nfts)

            # Normalize Decimal-like values to float
            serialized = []
            for n in nfts:
                serialized.append({
                    "id": n.get("id"),
                    "title": n.get("title"),
                    "description": n.get("description"),
                    "image_url": n.get("image_url"),
                    "price_inr": float(n.get("price_inr")) if n.get("price_inr") is not None else None,
                    "price_usd": float(n.get("price_usd")) if n.get("price_usd") is not None else None,
                    "category": n.get("category"),
                    "is_sold": n.get("is_sold", False),
                    "is_reserved": n.get("is_reserved", False),
                    "reserved_at": n.get("reserved_at"),
                    "sold_at": n.get("sold_at"),
                    "owner_id": n.get("owner_id"),
                    "created_at": n.get("created_at"),
                })

            return {
                "success": True,
                "message": "NFTs retrieved successfully",
                "data": {
                    "nfts": serialized,
                    "total": int(total),
                    "skip": skip,
                    "limit": limit
                }
            }
    except Exception as e:
        # If Supabase errors, log and fall back to local DB
        logger.warning(f"Supabase list_nfts failed, falling back to DB: {e}")

    # Fallback to existing local DB implementation
    try:
        query = db.query(NFT).filter(NFT.is_sold == False)
        if category:
            query = query.filter(NFT.category == category)
        total = query.count()
        nfts = query.offset(skip).limit(limit).all()

        serialized = []
        for n in nfts:
            serialized.append({
                "id": n.id,
                "title": n.title,
                "description": n.description,
                "image_url": n.image_url,
                "price_inr": float(n.price_inr) if n.price_inr is not None else None,
                "price_usd": float(n.price_usd) if n.price_usd is not None else None,
                "category": n.category,
                "is_sold": n.is_sold,
                "is_reserved": n.is_reserved,
                "reserved_at": n.reserved_at,
                "sold_at": n.sold_at,
                "owner_id": n.owner_id,
                "created_at": n.created_at
            })

        return {
            "success": True,
            "message": "NFTs retrieved successfully",
            "data": {
                "nfts": serialized,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        }
    except Exception as e:
        logger.error(f"Error listing NFTs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve NFTs"
        )

@router.get("/{nft_id}", response_model=NFTDetailResponse)
async def get_nft(nft_id: int, db: Session = Depends(get_db)):
    """Get specific NFT details. Prefer Supabase if configured, else fallback to local DB."""
    # Try Supabase first
    try:
        sb = get_supabase()
        if sb is not None:
            resp = sb.table("nfts").select("*").eq("id", nft_id).single().execute()
            nft = getattr(resp, "data", None)
            if nft:
                # Return in wrapper format with data as ORM-like dict
                return {
                    "success": True,
                    "message": "NFT retrieved successfully",
                    "data": {
                        "id": nft.get("id"),
                        "title": nft.get("title"),
                        "description": nft.get("description"),
                        "image_url": nft.get("image_url"),
                        "price_inr": nft.get("price_inr"),
                        "price_usd": nft.get("price_usd"),
                        "category": nft.get("category"),
                        "is_sold": nft.get("is_sold", False),
                        "is_reserved": nft.get("is_reserved", False),
                        "reserved_at": nft.get("reserved_at"),
                        "sold_at": nft.get("sold_at"),
                        "owner_id": nft.get("owner_id"),
                        "created_at": nft.get("created_at"),
                    }
                }
            # If not found in Supabase, fall through to local DB to preserve legacy data
    except Exception as e:
        logger.warning(f"Supabase get_nft failed, falling back to DB: {e}")

    # Fallback to local DB
    nft = db.query(NFT).filter(NFT.id == nft_id).first()
    if not nft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NFT not found"
        )
    return {
        "success": True,
        "message": "NFT retrieved successfully",
        "data": nft
    }

@router.post("/{nft_id}/buy")
async def buy_nft(
    nft_id: int,
    payment_mode: str | None = Query(None, description="Payment mode as query: 'INR' or 'USD'"),
    payload: BuyRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate NFT purchase (local DB transaction tracking).
    Accepts payment_mode via query param or JSON body.
    """
    # Merge payment_mode from query/body
    mode = payment_mode or (payload.payment_mode if payload else None)
    if not mode:
        raise HTTPException(status_code=422, detail="payment_mode is required in query or body")
    mode = mode.upper()

    nft = db.query(NFT).filter(NFT.id == nft_id).first()

    if not nft:
        # Optional: if using Supabase as source of truth and local mirror absent, we could allow purchase
        # only if NFT exists in Supabase and then create a shadow record. For now, keep behavior.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="NFT not found"
        )

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

    # Determine amount based on payment mode
    if mode == "INR":
        amount = nft.price_inr
        currency = "INR"
    elif mode == "USD":
        amount = nft.price_usd
        currency = "USD"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment mode. Use 'INR' or 'USD'"
        )

    # Create transaction
    transaction = Transaction(
        user_id=current_user.id,
        nft_id=nft_id,
        payment_mode=mode,
        amount=amount,
        currency=currency,
        payment_status="pending"
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # Reserve NFT for INR payments
    if mode == "INR":
        nft.is_reserved = True
        nft.reserved_at = transaction.created_at
        db.commit()

    return {
        "success": True,
        "message": "Purchase initiated successfully",
        "data": {
            "transaction_id": transaction.id,
            "payment_mode": mode,
            "amount": float(amount) if amount is not None else None,
            "currency": currency,
            "next_step": "complete_payment" if mode == "USD" else "await_payment_confirmation"
        }
    }

# -----------------------------
# Additional endpoints for frontend
# -----------------------------

@router.get("/search")
async def search_nfts(
    search: str = Query("", min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search NFTs by title/description. Supabase first, fallback to DB."""
    try:
        sb = get_supabase()
        if sb is not None:
            # PostgREST 'or' filter with ilike on title/description
            pattern = f"%{search}%"
            q = sb.table("nfts").select("*").or_(f"title.ilike.{pattern},description.ilike.{pattern}")
            q = q.eq("is_sold", False).limit(limit)
            resp = q.execute()
            rows = resp.data or []
            items = []
            for n in rows:
                items.append({
                    "id": n.get("id"),
                    "title": n.get("title"),
                    "description": n.get("description"),
                    "image_url": n.get("image_url"),
                    "price_inr": float(n.get("price_inr")) if n.get("price_inr") is not None else None,
                    "price_usd": float(n.get("price_usd")) if n.get("price_usd") is not None else None,
                    "category": n.get("category"),
                    "is_sold": n.get("is_sold", False),
                    "is_reserved": n.get("is_reserved", False),
                    "reserved_at": n.get("reserved_at"),
                    "sold_at": n.get("sold_at"),
                    "owner_id": n.get("owner_id"),
                    "created_at": n.get("created_at"),
                })
            return {"success": True, "message": "Search results", "data": {"nfts": items}}
    except Exception as e:
        logger.warning(f"Supabase search_nfts failed, falling back to DB: {e}")

    try:
        # Fallback to DB search (simple ilike on title/description)
        from sqlalchemy import or_
        query = db.query(NFT).filter(
            (NFT.title.ilike(f"%{search}%")) | (NFT.description.ilike(f"%{search}%"))
        ).filter(NFT.is_sold == False).limit(limit)
        nfts = query.all()
        items = []
        for n in nfts:
            items.append({
                "id": n.id,
                "title": n.title,
                "description": n.description,
                "image_url": n.image_url,
                "price_inr": float(n.price_inr) if n.price_inr is not None else None,
                "price_usd": float(n.price_usd) if n.price_usd is not None else None,
                "category": n.category,
                "is_sold": n.is_sold,
                "is_reserved": n.is_reserved,
                "reserved_at": n.reserved_at,
                "sold_at": n.sold_at,
                "owner_id": n.owner_id,
                "created_at": n.created_at,
            })
        return {"success": True, "message": "Search results", "data": {"nfts": items}}
    except Exception as e:
        logger.error(f"DB search_nfts failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

@router.get("/categories")
async def get_categories(db: Session = Depends(get_db)):
    """Return list of available NFT categories."""
    try:
        sb = get_supabase()
        if sb is not None:
            resp = sb.table("nfts").select("category", distinct=True).execute()
            rows = resp.data or []
            cats = [r.get("category") for r in rows if r.get("category")]
            # Ensure unique and sorted
            cats = sorted({c for c in cats})
            return {"success": True, "message": "Categories retrieved", "data": {"categories": cats}}
    except Exception as e:
        logger.warning(f"Supabase get_categories failed, falling back to DB: {e}")

    try:
        from sqlalchemy import distinct
        rows = db.query(distinct(NFT.category)).filter(NFT.category.isnot(None)).all()
        cats = sorted({r[0] for r in rows if r[0]})
        return {"success": True, "message": "Categories retrieved", "data": {"categories": cats}}
    except Exception as e:
        logger.error(f"DB get_categories failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch categories")

@router.get("/featured")
async def get_featured(limit: int = Query(8, ge=1, le=50), db: Session = Depends(get_db)):
    """Return featured NFTs (recent unsold)."""
    try:
        sb = get_supabase()
        if sb is not None:
            resp = (
                sb.table("nfts")
                .select("*")
                .eq("is_sold", False)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = resp.data or []
            items = []
            for n in rows:
                items.append({
                    "id": n.get("id"),
                    "title": n.get("title"),
                    "description": n.get("description"),
                    "image_url": n.get("image_url"),
                    "price_inr": float(n.get("price_inr")) if n.get("price_inr") is not None else None,
                    "price_usd": float(n.get("price_usd")) if n.get("price_usd") is not None else None,
                    "category": n.get("category"),
                    "is_sold": n.get("is_sold", False),
                    "is_reserved": n.get("is_reserved", False),
                    "reserved_at": n.get("reserved_at"),
                    "sold_at": n.get("sold_at"),
                    "owner_id": n.get("owner_id"),
                    "created_at": n.get("created_at"),
                })
            return {"success": True, "message": "Featured NFTs", "data": {"nfts": items}}
    except Exception as e:
        logger.warning(f"Supabase get_featured failed, falling back to DB: {e}")

    try:
        nfts = (
            db.query(NFT)
            .filter(NFT.is_sold == False)
            .order_by(NFT.created_at.desc())
            .limit(limit)
            .all()
        )
        items = []
        for n in nfts:
            items.append({
                "id": n.id,
                "title": n.title,
                "description": n.description,
                "image_url": n.image_url,
                "price_inr": float(n.price_inr) if n.price_inr is not None else None,
                "price_usd": float(n.price_usd) if n.price_usd is not None else None,
                "category": n.category,
                "is_sold": n.is_sold,
                "is_reserved": n.is_reserved,
                "reserved_at": n.reserved_at,
                "sold_at": n.sold_at,
                "owner_id": n.owner_id,
                "created_at": n.created_at,
            })
        return {"success": True, "message": "Featured NFTs", "data": {"nfts": items}}
    except Exception as e:
        logger.error(f"DB get_featured failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch featured")

@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Return aggregate NFT stats."""
    try:
        sb = get_supabase()
        if sb is not None:
            # totals via count
            total_resp = sb.table("nfts").select("id", count="exact").execute()
            total_nfts = int(getattr(total_resp, "count", 0) or 0)
            sold_resp = sb.table("nfts").select("id", count="exact").eq("is_sold", True).execute()
            total_sold = int(getattr(sold_resp, "count", 0) or 0)

            # revenue and average client-side
            prices_resp = sb.table("nfts").select("price_usd,is_sold").execute()
            rows = prices_resp.data or []
            sold_prices = [float(r.get("price_usd") or 0) for r in rows if r.get("is_sold")]
            all_prices = [float(r.get("price_usd") or 0) for r in rows]
            total_revenue = float(sum(sold_prices))
            average_price = float(sum(all_prices) / len(all_prices)) if all_prices else 0.0
            return {
                "success": True,
                "message": "Stats retrieved",
                "data": {
                    "total_nfts": total_nfts,
                    "total_sold": total_sold,
                    "total_revenue": total_revenue,
                    "average_price": average_price,
                },
            }
    except Exception as e:
        logger.warning(f"Supabase get_stats failed, falling back to DB: {e}")

    try:
        from sqlalchemy import func
        total_nfts = db.query(func.count(NFT.id)).scalar() or 0
        total_sold = db.query(func.count(NFT.id)).filter(NFT.is_sold == True).scalar() or 0
        total_revenue = db.query(func.coalesce(func.sum(NFT.price_usd), 0)).filter(NFT.is_sold == True).scalar() or 0
        avg_price = db.query(func.coalesce(func.avg(NFT.price_usd), 0)).scalar() or 0
        return {
            "success": True,
            "message": "Stats retrieved",
            "data": {
                "total_nfts": int(total_nfts),
                "total_sold": int(total_sold),
                "total_revenue": float(total_revenue),
                "average_price": float(avg_price),
            },
        }
    except Exception as e:
        logger.error(f"DB get_stats failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stats")

@router.get("/my-purchases")
async def my_purchases(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return NFTs purchased by the current user.
    Uses local DB where transactions are recorded.
    """
    try:
        # NFTs where user is owner
        owned = db.query(NFT).filter(NFT.owner_id == current_user.id).all()
        # NFTs with completed transactions by user
        completed_statuses = ("completed", "paid", "success")
        tx_join = (
            db.query(NFT)
            .join(Transaction, Transaction.nft_id == NFT.id)
            .filter(Transaction.user_id == current_user.id)
            .filter(Transaction.payment_status.in_(completed_statuses))
            .all()
        )
        # Merge unique by id
        by_id = {}
        for n in owned + tx_join:
            by_id[n.id] = n
        items = []
        for n in by_id.values():
            items.append({
                "id": n.id,
                "title": n.title,
                "description": n.description,
                "image_url": n.image_url,
                "price_inr": float(n.price_inr) if n.price_inr is not None else None,
                "price_usd": float(n.price_usd) if n.price_usd is not None else None,
                "category": n.category,
                "is_sold": n.is_sold,
                "is_reserved": n.is_reserved,
                "reserved_at": n.reserved_at,
                "sold_at": n.sold_at,
                "owner_id": n.owner_id,
                "created_at": n.created_at,
            })
        return {"success": True, "message": "Purchases retrieved", "data": {"nfts": items}}
    except Exception as e:
        logger.error(f"my_purchases failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch purchases")
