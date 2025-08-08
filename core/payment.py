import httpx
import json
import logging
from typing import Dict, Any
from fastapi import HTTPException, status

from config.settings import settings
from models.transaction import Transaction

logger = logging.getLogger(__name__)

async def process_paypal_payment(transaction: Transaction) -> Dict[str, Any]:
    """Create PayPal payment for USD transactions"""
    
    # Get PayPal access token
    access_token = await get_paypal_access_token()
    
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get PayPal access token"
        )
    
    # Create payment payload
    payment_payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": str(transaction.id),
            "amount": {
                "currency_code": transaction.currency,
                "value": str(transaction.amount)
            },
            "description": f"NFT Purchase - Transaction {transaction.id}",
            "custom_id": str(transaction.id)
        }],
        "payment_source": {
            "paypal": {
                "experience_context": {
                    "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                    "brand_name": "NFT Marketplace",
                    "locale": "en-US",
                    "landing_page": "LOGIN",
                    "shipping_preference": "NO_SHIPPING",
                    "user_action": "PAY_NOW",
                    "return_url": f"{settings.FRONTEND_URL}/payment/success",
                    "cancel_url": f"{settings.FRONTEND_URL}/payment/cancel"
                }
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "PayPal-Request-Id": f"nft-{transaction.id}-{transaction.created_at.timestamp()}"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders",
            json=payment_payload,
            headers=headers
        )
    
    if response.status_code != 201:
        logger.error(f"PayPal payment creation failed: {response.text}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create PayPal payment"
        )
    
    payment_data = response.json()
    
    # Extract approval URL
    approval_url = None
    for link in payment_data.get("links", []):
        if link.get("rel") == "approve":
            approval_url = link.get("href")
            break
    
    return {
        "payment_id": payment_data.get("id"),
        "approval_url": approval_url,
        "status": payment_data.get("status")
    }

async def get_paypal_access_token() -> str:
    """Get PayPal access token"""
    try:
        auth_data = {
            "grant_type": "client_credentials"
        }
        
        auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET)
        
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token",
                data=auth_data,
                headers=headers,
                auth=auth
            )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            logger.error(f"PayPal token request failed: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting PayPal access token: {e}")
        return None

def verify_paypal_webhook(body: bytes, headers: Dict[str, str]) -> bool:
    """Verify PayPal webhook signature"""
    # In production, implement proper webhook signature verification
    # For now, return True for development
    # TODO: Implement PayPal webhook signature verification
    return True
