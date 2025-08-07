from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List
import logging

from app.db.session import get_db
from app.models.nft import NFT
from app.models.analytics import Analytics
from app.models.pydantic_models import NFTResponse, PaginationInfo, AnalyticsEvent
from app.routes.auth import get_current_user, get_current_admin_user, get_current_user_optional
from app.models.user import User
from app.utils.response import success_response, error_response
from app.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nfts", tags=["nfts"])

@router.get("", response_model=dict)
async def list_nfts(
    page: int = Query(1, ge=1),
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    category: Optional[str] = Query(None),
    min_price_inr: Optional[float] = Query(None, ge=0),
    max_price_inr: Optional[float] = Query(None, ge=0),
    min_price_usd: Optional[float] = Query(None, ge=0),
    max_price_usd: Optional[float] = Query(None, ge=0),
    sort: Optional[str] = Query("created_at:desc"),
    include_sold: bool = Query(False),
    db: Session = Depends(get_db)
):
    """List NFTs with pagination and filters"""
    try:
        # Build query
        query = db.query(NFT)
        
        # Apply filters
        if not include_sold:
            query = query.filter(NFT.is_sold == False)
        
        if category:
            query = query.filter(NFT.category == category)
        
        if min_price_inr is not None:
            query = query.filter(NFT.price_inr >= min_price_inr)
        
        if max_price_inr is not None:
            query = query.filter(NFT.price_inr <= max_price_inr)
        
        if min_price_usd is not None:
            query = query.filter(NFT.price_usd >= min_price_usd)
        
        if max_price_usd is not None:
            query = query.filter(NFT.price_usd <= max_price_usd)
        
        # Apply sorting
        if sort:
            if ":" in sort:
                field, direction = sort.split(":")
                if field in ["price_inr", "price_usd", "created_at", "title"]:
                    order_field = getattr(NFT, field)
                    if direction.lower() == "desc":
                        query = query.order_by(order_field.desc())
                    else:
                        query = query.order_by(order_field.asc())
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * size
        nfts = query.offset(offset).limit(size).all()
        
        # Convert to response format
        nft_responses = [NFTResponse.model_validate(nft).model_dump() for nft in nfts]
        
        # Calculate pagination info
        total_pages = (total + size - 1) // size
        pagination = PaginationInfo(
            total=total,
            page=page,
            size=size,
            pages=total_pages
        )
        
        return success_response({
            "nfts": nft_responses,
            "pagination": pagination.model_dump()
        })
        
    except Exception as e:
        logger.error(f"Error listing NFTs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve NFTs"
        )

@router.get("/{nft_id}", response_model=dict)
async def get_nft(
    nft_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)  # Optional auth
):
    """Get NFT details by ID"""
    try:
        nft = db.query(NFT).filter(NFT.id == nft_id).first()
        
        if not nft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NFT not found"
            )
        
        # Track view analytics if user is authenticated
        if current_user:
            try:
                analytics_event = Analytics(
                    nft_id=nft_id,
                    user_id=current_user.id,
                    event_type="view",
                    event_data={"nft_title": nft.title}
                )
                db.add(analytics_event)
                db.commit()
            except Exception as e:
                logger.warning(f"Failed to track analytics: {e}")
        
        nft_response = NFTResponse.model_validate(nft)
        return success_response(nft_response.model_dump())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting NFT {nft_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve NFT"
        )

@router.get("/categories/list", response_model=dict)
async def list_categories(db: Session = Depends(get_db)):
    """Get list of available NFT categories"""
    try:
        categories = db.query(NFT.category).distinct().filter(
            NFT.category.isnot(None),
            NFT.is_sold == False
        ).all()
        
        category_list = [cat[0] for cat in categories if cat[0]]
        
        return success_response({"categories": category_list})
        
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve categories"
        )

@router.post("/{nft_id}/track-view")
async def track_nft_view(
    nft_id: int,
    event_data: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)  # Optional for anonymous tracking
):
    """Track NFT view for analytics"""
    try:
        # Verify NFT exists
        nft = db.query(NFT).filter(NFT.id == nft_id).first()
        if not nft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="NFT not found"
            )
        
        # Create analytics event
        analytics_event = Analytics(
            nft_id=nft_id,
            user_id=current_user.id if current_user else None,
            event_type="view",
            event_data=event_data or {}
        )
        
        db.add(analytics_event)
        db.commit()
        
        return success_response(message="View tracked successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking view for NFT {nft_id}: {e}")
        # Don't raise exception for analytics failures
        return success_response(message="View tracking failed silently")
