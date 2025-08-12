import os
import requests
import pytest

BASE_URL = os.getenv("PAYMENT_TEST_BASE_URL", "http://localhost:8000")
NFT_ID = 1
AMOUNT = "25.00"
CURRENCY = "USD"
BUYER_EMAIL = "sb-sp7aj45081963@personal.example.com"
BUYER_NAME = "John Doe"


def _paypal_creds_available() -> bool:
    return bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET"))


@pytest.fixture(scope="module")
def order_id():
    """Create a PayPal order and return its ID. Skips if creds/server not ready."""
    if not _paypal_creds_available():
        pytest.skip("Skipping PayPal tests: PAYPAL_CLIENT_ID/SECRET not set")

    try:
        resp = requests.post(
            f"{BASE_URL}/api/payment/paypal/create",
            json={
                "nft_id": NFT_ID,
                "amount": AMOUNT,
                "currency": CURRENCY,
                "return_url": "http://localhost:3000/purchase/success",
                "cancel_url": "http://localhost:3000/purchase/cancel",
            },
            timeout=20,
        )
    except Exception as e:
        pytest.skip(f"Cannot reach backend at {BASE_URL}: {e}")

    if resp.status_code != 200:
        # Common when creds are invalid or PayPal API is unavailable in CI
        pytest.skip(f"Create order failed: {resp.status_code} {resp.text[:200]}")

    data = resp.json()
    assert data.get("success"), f"Order not successful: {data}"
    oid = data["order"]["id"]
    print(f"Order created: {oid}")
    return oid


def test_create_paypal_order(order_id):
    """Validate that order creation returns a non-empty order id."""
    assert isinstance(order_id, str) and len(order_id) > 0


def test_capture_paypal_order(order_id):
    """Optional: capture requires manual approval. Provide APPROVED_ORDER_ID to run."""
    approved_order_id = os.getenv("APPROVED_ORDER_ID") or None
    if not approved_order_id:
        pytest.skip(
            "Skipping capture: set APPROVED_ORDER_ID to a sandbox-approved order id"
        )

    resp = requests.post(
        f"{BASE_URL}/api/payment/paypal/capture",
        json={
            "orderID": approved_order_id,
            "nft_id": NFT_ID,
            "buyer_email": BUYER_EMAIL,
            "buyer_name": BUYER_NAME,
        },
        timeout=20,
    )
    assert resp.status_code == 200, f"Capture failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data.get("success"), f"Capture not successful: {data}"


if __name__ == "__main__":
    # Manual run flow for local debugging
    try:
        oid = requests.post(
            f"{BASE_URL}/api/payment/paypal/create",
            json={
                "nft_id": NFT_ID,
                "amount": AMOUNT,
                "currency": CURRENCY,
                "return_url": "http://localhost:3000/purchase/success",
                "cancel_url": "http://localhost:3000/purchase/cancel",
            },
            timeout=20,
        ).json()["order"]["id"]
    except Exception as e:
        raise SystemExit(f"Failed to create order: {e}")

    input(f"Approve order {oid} in PayPal sandbox, then press Enter to continue...")
    r = requests.post(
        f"{BASE_URL}/api/payment/paypal/capture",
        json={
            "orderID": oid,
            "nft_id": NFT_ID,
            "buyer_email": BUYER_EMAIL,
            "buyer_name": BUYER_NAME,
        },
        timeout=20,
    )
    print("Capture response:", r.status_code, r.text)
    print("PayPal integration test completed.")
