"""
Bulk import images and metadata into Supabase Storage and the `nfts` table.

Usage examples:
  python import_to_supabase.py --images-dir ./new_images --metadata metadata.csv --bucket nft-images --make-public
  python import_to_supabase.py --images-dir ./new_images --metadata metadata.json --bucket nft-images --create-local

Metadata CSV/JSON expected fields (per item):
  filename,title,description,price_inr,price_usd,category,image_url

If metadata is not provided, the script will attempt to upload all files in the directory using
filename-based defaults (title = filename, price_usd=0, price_inr=0, category='uncategorized').

This script uses the project's Supabase settings (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY / ANON key)
from config.settings. For local DB shadow insertion set --create-local and ensure env/.env is configured.
"""

import argparse
import json
import csv
from pathlib import Path
import mimetypes
import logging
from typing import Dict, Optional

from config.settings import settings
from utilities.supabase_client import get_supabase

logger = logging.getLogger("import_to_supabase")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Optional local DB shadowing
try:
    from db.session import SessionLocal
    from models.nft import NFT
    from models.user import User
    LOCAL_DB_AVAILABLE = True
except Exception:
    LOCAL_DB_AVAILABLE = False


def load_metadata(metadata_path: Optional[Path]) -> Dict[str, Dict]:
    items = {}
    if not metadata_path:
        return items
    if not metadata_path.exists():
        logger.warning("Metadata file %s not found", metadata_path)
        return items
    if metadata_path.suffix.lower() in (".json",):
        data = json.loads(metadata_path.read_text(encoding='utf-8'))
        # Expect either a list or dict keyed by filename
        if isinstance(data, list):
            for r in data:
                fn = r.get('filename') or r.get('file') or r.get('image')
                if not fn:
                    continue
                items[fn] = r
        elif isinstance(data, dict):
            # assume mapping filename -> meta
            for k, v in data.items():
                items[k] = v
    elif metadata_path.suffix.lower() in (".csv",):
        with open(metadata_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                fn = row.get('filename') or row.get('file')
                if not fn:
                    continue
                items[fn] = row
    else:
        logger.warning("Unsupported metadata file type: %s", metadata_path.suffix)
    return items


def get_public_url(sb, bucket: str, path: str) -> Optional[str]:
    try:
        # supabase client v2 storage API
        res = sb.storage.from_(bucket).get_public_url(path)
        # get_public_url may return dict or object depending on client; be defensive
        if isinstance(res, dict):
            return res.get('publicUrl') or res.get('public_url')
        # some clients return object with 'public_url'
        return getattr(res, 'public_url', None) or getattr(res, 'publicUrl', None)
    except Exception as e:
        logger.warning("get_public_url failed: %s", e)
        return None


def upload_file(sb, bucket: str, local_path: Path, dest_path: str, make_public: bool = True) -> Optional[str]:
    try:
        with open(local_path, 'rb') as f:
            content = f.read()
        content_type = mimetypes.guess_type(local_path.name)[0] or 'application/octet-stream'
        logger.info("Uploading %s -> %s/%s", local_path, bucket, dest_path)
        # supabase-py v2 uses file_options for headers; fallback without options if it fails
        try:
            sb.storage.from_(bucket).upload(dest_path, content, file_options={"content-type": content_type, "x-upsert": "true"})
        except TypeError:
            # Older signature without file_options
            sb.storage.from_(bucket).upload(dest_path, content)
        except Exception as e:
            logger.error("Raw upload failed: %s", e)
            return None
        # Bucket-level public setting typically controls access; still derive public URL
        url = None
        if make_public:
            url = get_public_url(sb, bucket, dest_path)
        return url or dest_path
    except Exception as e:
        logger.error("Failed to upload %s: %s", local_path, e)
        return None


def insert_nft_row(sb, record: Dict, upsert: bool = False) -> Optional[Dict]:
    try:
        table = sb.table('nfts')
        if upsert and hasattr(table, 'upsert'):
            res = table.upsert(record).execute()
        else:
            res = table.insert(record).execute()
        data = getattr(res, 'data', None) or (res if isinstance(res, dict) else None)
        logger.info("%s row in nfts: %s", "Upserted" if upsert else "Inserted", data)
        return data
    except Exception as e:
        logger.error("Failed to write nft row: %s", e)
        return None


def create_local_shadow(db_session, record: Dict):
    if not LOCAL_DB_AVAILABLE:
        logger.warning("Local DB not available; skipping shadow creation")
        return
    try:
        db = db_session()
        nft = NFT(
            id=record.get('id'),
            title=record.get('title') or '',
            description=record.get('description') or '',
            image_url=record.get('image_url') or '',
            price_inr=record.get('price_inr') or 0,
            price_usd=record.get('price_usd') or 0,
            category=record.get('category') or None,
            is_sold=record.get('is_sold', False),
            is_reserved=record.get('is_reserved', False),
        )
        db.add(nft)
        db.commit()
        db.refresh(nft)
        logger.info("Created local shadow NFT id=%s", nft.id)
    except Exception as e:
        logger.warning("Failed to create local shadow: %s", e)


def main():
    parser = argparse.ArgumentParser(description="Import images and metadata to Supabase and nfts table")
    parser.add_argument('--images-dir', required=True, help='Directory containing image files')
    parser.add_argument('--metadata', help='Optional metadata file (CSV or JSON)')
    parser.add_argument('--bucket', default='nft-images', help='Supabase storage bucket name')
    parser.add_argument('--make-public', action='store_true', help='Make uploaded images public and store public url')
    parser.add_argument('--create-local', action='store_true', help='Also create local DB shadow records')
    parser.add_argument('--prefix', default='nfts/', help='Path prefix inside storage bucket')
    parser.add_argument('--no-upload', action='store_true', help='Skip storage upload; only create/update DB rows')
    parser.add_argument('--upsert', action='store_true', help='Use upsert instead of insert (match on unique constraints)')
    parser.add_argument('--image-url-base', default='', help='Base URL to construct image_url when --no-upload (e.g. https://site/images)')
    args = parser.parse_args()

    images_dir = Path(args.images_dir)
    if not images_dir.exists() or not images_dir.is_dir():
        logger.error("images-dir %s not found or not a directory", images_dir)
        return

    metadata_path = Path(args.metadata) if args.metadata else None
    meta = load_metadata(metadata_path)

    sb = get_supabase()
    if not sb:
        logger.error("Supabase client not initialized. Check SUPABASE_URL and keys in .env")
        return

    # Ensure bucket exists? The supabase client doesn't always expose create_bucket in all envs.
    bucket = args.bucket

    files = [p for p in images_dir.iterdir() if p.is_file()]
    logger.info("Found %d files in %s", len(files), images_dir)

    for p in files:
        fn = p.name
        item_meta = meta.get(fn, {})
        title = item_meta.get('title') or p.stem
        description = item_meta.get('description') or ''
        price_inr = float(item_meta.get('price_inr') or item_meta.get('price') or 0)
        price_usd = float(item_meta.get('price_usd') or 0)
        category = item_meta.get('category') or 'uncategorized'

        dest_path = f"{args.prefix}{fn}"
        public_url = None
        if not args.no_upload:
            public_url = upload_file(sb, bucket, p, dest_path, make_public=args.make_public)
        else:
            if not args.image_url_base:
                # default to FRONTEND_URL/images/<filename>
                base = settings.FRONTEND_URL.rstrip('/') + '/images'
            else:
                base = args.image_url_base.rstrip('/')
            public_url = f"{base}/{fn}"
        image_url = public_url or item_meta.get('image_url') or dest_path

        record = {
            'title': title,
            'description': description,
            'image_url': image_url,
            'price_inr': price_inr,
            'price_usd': price_usd,
            'category': category,
            'is_sold': False,
            'is_reserved': False,
        }

        inserted = insert_nft_row(sb, record, upsert=args.upsert)
        # If Supabase returned inserted row with id, try to create local shadow
        if args.create_local:
            try:
                # If the inserted object is a list with one dict, normalize
                if isinstance(inserted, list) and len(inserted) > 0:
                    created = inserted[0]
                elif isinstance(inserted, dict):
                    created = inserted
                else:
                    created = record
                # map id and image_url
                created_record = {
                    'id': created.get('id') if isinstance(created, dict) else None,
                    'title': created.get('title') if isinstance(created, dict) else record['title'],
                    'description': created.get('description') if isinstance(created, dict) else record['description'],
                    'image_url': created.get('image_url') if isinstance(created, dict) else record['image_url'],
                    'price_inr': created.get('price_inr') if isinstance(created, dict) else record['price_inr'],
                    'price_usd': created.get('price_usd') if isinstance(created, dict) else record['price_usd'],
                    'category': created.get('category') if isinstance(created, dict) else record['category'],
                    'is_sold': created.get('is_sold') if isinstance(created, dict) else record['is_sold'],
                }
                create_local_shadow(SessionLocal, created_record)
            except Exception as e:
                logger.warning("Local shadow creation workflow failed: %s", e)

    logger.info("Import complete")


if __name__ == '__main__':
    main()
