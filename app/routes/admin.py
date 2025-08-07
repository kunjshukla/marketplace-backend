from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from app.db.session import get_db
from app.models.user import User
from app.models.nft import NFT
from app.models.transaction import Transaction
from app.models.analytics import Analytics
from app.models.pydantic_models import (
    NFTCreate, NFTUpdate, NFTResponse, TransactionResponse,
    TransactionVerificationRequest, AnalyticsResponse
)
from app.routes.auth import get_current_admin_user
from app.utils.response import success_response, error_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/nft/create", response_model=dict)
async def create_nft(
    nft_data: NFTCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new NFT (Admin only)"""
    try:
        nft = NFT(
            title=nft_data.title,
            image_url=nft_data.image_url,
            price_inr=nft_data.price_inr,
            price_usd=nft_data.price_usd,
            category=nft_data.category
        )
        
        db.add(nft)
        db.commit()
        db.refresh(nft)
        
        # Track analytics
        analytics_event = Analytics(
            user_id=current_admin.id,
            nft_id=nft.id,
            event_type="nft_created",
            event_data={"title": nft.title, "category": nft.category}
        )
        db.add(analytics_event)
        db.commit()
        
        logger.info(f"Admin {current_admin.id} created NFT {nft.id}")
        
        return success_response(
            data={"nft_id": nft.id},
            message="NFT created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error creating NFT: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create NFT"
        )

@router.put("/nft/{nft_id}", response_model=dict)
async def update_nft(
    nft_id: int,
    nft_data: NFTUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update an existing NFT (Admin only)"""
    try:
        nft = db.query(NFT).filter(NFT.id == nft_id).first()
        if not nft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NFT not found"
            )
        
        # Don't allow updating sold NFTs
        if nft.is_sold:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update sold NFT"
            )
        
        # Update fields
        update_data = nft_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(nft, field, value)
        
        db.commit()
        
        # Track analytics
        analytics_event = Analytics(
            user_id=current_admin.id,
            nft_id=nft.id,
            event_type="nft_updated",
            event_data={"updated_fields": list(update_data.keys())}
        )
        db.add(analytics_event)
        db.commit()
        
        logger.info(f"Admin {current_admin.id} updated NFT {nft.id}")
        
        return success_response(message="NFT updated successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating NFT {nft_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update NFT"
        )

@router.delete("/nft/{nft_id}", response_model=dict)
async def delete_nft(
    nft_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete an NFT (Admin only)"""
    try:
        nft = db.query(NFT).filter(NFT.id == nft_id).first()
        if not nft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NFT not found"
            )
        
        # Don't allow deleting sold NFTs
        if nft.is_sold:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete sold NFT"
            )
        
        # Check for pending transactions
        pending_transactions = db.query(Transaction).filter(
            Transaction.nft_id == nft_id,
            Transaction.status == "pending"
        ).count()
        
        if pending_transactions > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete NFT with pending transactions"
            )
        
        db.delete(nft)
        db.commit()
        
        # Track analytics
        analytics_event = Analytics(
            user_id=current_admin.id,
            event_type="nft_deleted",
            event_data={"nft_id": nft_id, "title": nft.title}
        )
        db.add(analytics_event)
        db.commit()
        
        logger.info(f"Admin {current_admin.id} deleted NFT {nft_id}")
        
        return success_response(message="NFT deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting NFT {nft_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete NFT"
        )

@router.get("/transactions", response_model=dict)
async def list_pending_transactions(
    status_filter: Optional[str] = Query("pending"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """List transactions for admin verification"""
    try:
        query = db.query(Transaction).join(NFT).join(User)
        
        if status_filter:
            query = query.filter(Transaction.status == status_filter)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * size
        transactions = query.order_by(desc(Transaction.created_at))\
                          .offset(offset).limit(size).all()
        
        # Format response
        transaction_data = []
        for txn in transactions:
            nft = db.query(NFT).filter(NFT.id == txn.nft_id).first()
            user = db.query(User).filter(User.id == txn.user_id).first()
            
            transaction_data.append({
                "id": txn.id,
                "nft_id": txn.nft_id,
                "nft_title": nft.title if nft else "Unknown",
                "user_id": txn.user_id,
                "user_name": user.name if user else "Unknown",
                "user_email": user.email if user else "Unknown",
                "payment_method": txn.payment_method,
                "status": txn.status,
                "buyer_currency": txn.buyer_currency,
                "amount": float(nft.price_inr if txn.payment_method == "INR" else nft.price_usd) if nft else 0,
                "txn_ref": txn.txn_ref,
                "created_at": txn.created_at.isoformat()
            })
        
        return success_response(
            data={
                "transactions": transaction_data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "size": size,
                    "pages": (total + size - 1) // size
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transactions"
        )

@router.post("/verify-transaction/{transaction_id}", response_model=dict)
async def verify_transaction(
    transaction_id: int,
    verification: TransactionVerificationRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Verify INR transaction (Admin only)"""
    try:
        # Get transaction
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.payment_method == "INR"
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        if transaction.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction already processed"
            )
        
        # Get NFT and user
        nft = db.query(NFT).filter(NFT.id == transaction.nft_id).first()
        user = db.query(User).filter(User.id == transaction.user_id).first()
        
        if not nft or not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated NFT or user not found"
            )
        
        # Update transaction status
        transaction.status = verification.status
        
        if verification.status == "paid":
            # Mark NFT as sold
            nft.is_sold = True
            nft.sold_to_user_id = user.id
            nft.is_reserved = False
            nft.reserved_at = None
            
            # Track successful purchase
            analytics_event = Analytics(
                user_id=user.id,
                nft_id=nft.id,
                event_type="purchase_completed",
                event_data={
                    "transaction_id": transaction.id,
                    "payment_method": "INR",
                    "amount_inr": float(nft.price_inr),
                    "verified_by": current_admin.id
                }
            )
            db.add(analytics_event)
            
            logger.info(f"Admin {current_admin.id} verified transaction {transaction_id} as paid")
            
        elif verification.status == "failed":
            # Release reservation
            nft.is_reserved = False
            nft.reserved_at = None
            
            logger.info(f"Admin {current_admin.id} marked transaction {transaction_id} as failed")
        
        # Track admin action
        admin_analytics = Analytics(
            user_id=current_admin.id,
            nft_id=nft.id,
            event_type="admin_verification",
            event_data={
                "transaction_id": transaction.id,
                "verification_status": verification.status,
                "user_id": user.id
            }
        )
        db.add(admin_analytics)
        db.commit()
        
        return success_response(
            data={"status": verification.status},
            message=f"Transaction {verification.status} successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying transaction {transaction_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify transaction"
        )

@router.get("/analytics", response_model=dict)
async def get_analytics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get analytics report (Admin only)"""
    try:
        # Build query
        query = db.query(Analytics)
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Analytics.created_at >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Analytics.created_at <= end_dt)
        
        if event_type:
            query = query.filter(Analytics.event_type == event_type)
        
        # Get analytics data
        analytics_data = query.order_by(desc(Analytics.created_at)).limit(1000).all()
        
        # Generate summary statistics
        total_events = len(analytics_data)
        events_by_type = {}
        nft_views = {}
        purchase_events = 0
        
        for event in analytics_data:
            # Count by event type
            events_by_type[event.event_type] = events_by_type.get(event.event_type, 0) + 1
            
            # Count NFT views
            if event.event_type == "view" and event.nft_id:
                nft_views[event.nft_id] = nft_views.get(event.nft_id, 0) + 1
            
            # Count purchase events
            if event.event_type in ["purchase_inr_start", "purchase_usd_start", "purchase_completed"]:
                purchase_events += 1
        
        # Get top viewed NFTs
        top_nfts = []
        for nft_id, views in sorted(nft_views.items(), key=lambda x: x[1], reverse=True)[:10]:
            nft = db.query(NFT).filter(NFT.id == nft_id).first()
            if nft:
                top_nfts.append({
                    "nft_id": nft_id,
                    "title": nft.title,
                    "views": views
                })
        
        # Get recent transactions
        recent_transactions = db.query(Transaction)\
                               .order_by(desc(Transaction.created_at))\
                               .limit(10).all()
        
        transaction_summary = []
        for txn in recent_transactions:
            nft = db.query(NFT).filter(NFT.id == txn.nft_id).first()
            user = db.query(User).filter(User.id == txn.user_id).first()
            
            transaction_summary.append({
                "id": txn.id,
                "nft_title": nft.title if nft else "Unknown",
                "user_name": user.name if user else "Unknown",
                "status": txn.status,
                "payment_method": txn.payment_method,
                "created_at": txn.created_at.isoformat()
            })
        
        report = {
            "summary": {
                "total_events": total_events,
                "events_by_type": events_by_type,
                "purchase_events": purchase_events,
                "date_range": {
                    "start": start_date,
                    "end": end_date
                }
            },
            "top_nfts": top_nfts,
            "recent_transactions": transaction_summary
        }
        
        return success_response(data={"report": report})
        
    except Exception as e:
        logger.error(f"Error generating analytics report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate analytics report"
        )
