#!/usr/bin/env python3
"""
Database migration script for NFT Marketplace
Fixes missing columns and schema issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine
from app.config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

def run_migration():
    """Run database migration to fix schema issues"""
    try:
        with engine.connect() as conn:
            print("Connected to database successfully")
            
            # Add missing category column
            print("Adding category column to nfts table...")
            conn.execute(text("ALTER TABLE nfts ADD COLUMN IF NOT EXISTS category VARCHAR(100)"))
            
            # Add missing description column
            print("Adding description column to nfts table...")
            conn.execute(text("ALTER TABLE nfts ADD COLUMN IF NOT EXISTS description TEXT"))
            
            # Update existing NFTs with default category
            print("Updating existing NFTs with default category...")
            conn.execute(text("UPDATE nfts SET category = 'art' WHERE category IS NULL"))
            
            # Create indexes
            print("Creating performance indexes...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_nfts_category ON nfts(category)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_nfts_is_sold ON nfts(is_sold)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_nfts_is_reserved ON nfts(is_reserved)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_nfts_created_at ON nfts(created_at)"))
            
            # Commit changes
            conn.commit()
            print("✅ Migration completed successfully!")
            
            # Show table structure
            print("\nCurrent nfts table structure:")
            result = conn.execute(text("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'nfts' ORDER BY ordinal_position"))
            for row in result:
                print(f"  {row[0]}: {row[1]} {'NULL' if row[2] == 'YES' else 'NOT NULL'}")
                
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("NFT Marketplace Database Migration")
    print(f"Database URL: {DATABASE_URL}")
    print("=" * 50)
    run_migration()
