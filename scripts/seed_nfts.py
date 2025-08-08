"""Seed local NFT metadata into database.

Usage:
    python -m scripts.seed_nfts auto          # auto import images in backend/images
    python -m scripts.seed_nfts               # seed default list below
    python -m scripts.seed_nfts path/to/nfts.json   # optional JSON file

Note: Runtime auto-seeding removed from main.py; use this script explicitly.

JSON file format:
[
  {
    "title": "Genesis Art #1",
    "description": "First genesis NFT",
    "image_url": "https://your.cdn/genesis1.png",
    "price_inr": 4999.00,
    "price_usd": 59.99,
    "category": "art"
  }
]

If you have only local image files, place them in a served static folder and reference
via URL (e.g. http://localhost:8000/static/<file>). To serve a folder, you can mount
StaticFiles in FastAPI main.py:

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="images/nfts"), name="static")

Then set image_url to "/static/filename.png" (frontend should prefix backend origin).
"""
from __future__ import annotations
import sys, json, logging
from decimal import Decimal
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

# Allow running from project root or backend folder
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = CURRENT_DIR.parent
sys.path.append(str(BACKEND_ROOT))

from db.session import SessionLocal, create_tables, engine  # type: ignore
from models.nft import NFT  # type: ignore
# Ensure related models are registered so relationships resolve
import models.user  # type: ignore  # noqa: F401
import models.transaction  # type: ignore  # noqa: F401

# Create tables if not already present
try:
    create_tables()
except Exception as e:
    logging.warning("Could not create tables automatically: %s", e)

# NEW: ensure required NFT columns exist (in case legacy table missing them)
REQUIRED_COLUMNS_SQL = {
    'description': 'TEXT',
    'image_url': 'TEXT NOT NULL DEFAULT ""',
    'price_inr': 'DECIMAL(10,2) NOT NULL DEFAULT 0',
    'price_usd': 'DECIMAL(10,2) NOT NULL DEFAULT 0',
    'category': 'VARCHAR(100)',
    'is_sold': 'BOOLEAN NOT NULL DEFAULT FALSE',
    'is_reserved': 'BOOLEAN NOT NULL DEFAULT FALSE',
    'reserved_at': 'TIMESTAMPTZ',
    'sold_at': 'TIMESTAMPTZ',
    'owner_id': 'INTEGER',
    'created_at': 'TIMESTAMPTZ DEFAULT NOW()'
}

def ensure_nft_columns():
    try:
        insp = inspect(engine)
        if 'nfts' not in insp.get_table_names():
            logging.info("nfts table not found (will be created by metadata).")
            return
        existing = {c['name'] for c in insp.get_columns('nfts')}
        with engine.begin() as conn:
            for col, ddl in REQUIRED_COLUMNS_SQL.items():
                if col not in existing:
                    logging.info("Adding missing column %s", col)
                    conn.execute(text(f'ALTER TABLE nfts ADD COLUMN {col} {ddl}'))
    except Exception as e:
        logging.warning("Column ensure step failed: %s", e)

ensure_nft_columns()

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("seed_nfts")

# Default seed data (edit as needed)
DEFAULT_NFTS = [
    {
        "title": "Local Art #1",
        "description": "Sample local NFT 1",
        "image_url": "/static/local_art_1.png",  # adjust
        "price_inr": Decimal("2500.00"),
        "price_usd": Decimal("34.99"),
        "category": "art"
    },
    {
        "title": "Local Art #2",
        "description": "Sample local NFT 2",
        "image_url": "/static/local_art_2.png",
        "price_inr": Decimal("3500.00"),
        "price_usd": Decimal("44.99"),
        "category": "art"
    }
]

UNIQUE_KEY = "title"  # simple de-dupe field; change if needed
IMAGE_DIR = Path(__file__).resolve().parent.parent / "images"  # backend images folder
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp"}

# NEW: auto-generate entries from image folder

def build_from_images() -> list[dict]:
    if not IMAGE_DIR.exists():
        logging.warning("Image directory not found: %s", IMAGE_DIR)
        return []
    items = []
    for img in sorted(IMAGE_DIR.iterdir()):
        if img.is_file() and img.suffix.lower() in SUPPORTED_EXT:
            title = img.stem.replace("_", " ").title()
            items.append({
                "title": title,
                "description": f"Auto-imported NFT for {img.name}",
                "image_url": f"/static/{img.name}",
                "price_inr": Decimal("2500.00"),  # adjust pricing logic as needed
                "price_usd": Decimal("34.99"),
                "category": "imported"
            })
    return items

def load_input(path: Path | None):
    # If user passes the literal word 'auto', build from images
    if path and path.name.lower() == "auto":
        data = build_from_images()
        if not data:
            logging.warning("No images found for auto generation.")
        return data
    if not path:
        return DEFAULT_NFTS
    data = json.loads(path.read_text())
    return data

def seed(nfts):
    inserted = 0
    skipped = 0
    with SessionLocal() as db:  # type: Session
        for item in nfts:
            key_val = item.get(UNIQUE_KEY)
            if key_val and db.query(NFT).filter(getattr(NFT, UNIQUE_KEY)==key_val).first():
                skipped += 1
                continue
            nft = NFT(
                title=item["title"],
                description=item.get("description"),
                image_url=item["image_url"],
                price_inr=Decimal(str(item["price_inr"])),
                price_usd=Decimal(str(item["price_usd"])),
                category=item.get("category")
            )
            db.add(nft)
            inserted += 1
        db.commit()
    logger.info("Inserted %d NFTs, skipped %d (already existed).", inserted, skipped)

if __name__ == "__main__":
    # Allow: python -m scripts.seed_nfts auto
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    json_path = Path(arg) if arg and arg.lower() != "auto" else (Path("auto") if arg else None)
    if json_path and json_path.name != "auto" and not json_path.exists():
        logger.error("JSON file not found: %s", json_path)
        sys.exit(1)
    nft_list = load_input(json_path)
    if not nft_list:
        logger.info("Nothing to seed.")
        sys.exit(0)
    seed(nft_list)
    logger.info("Done.")
