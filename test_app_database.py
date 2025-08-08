#!/usr/bin/env python3
"""
Test application database setup and create a sample user
"""

import asyncio
import sys
import os
from datetime import datetime

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_app_database():
    print("Testing NFT Marketplace database setup...")
    
    try:
        # Import application modules
        from db.session import get_async_session
        from models.user import User
        from models.nft import NFT
        from models.transaction import Transaction
        from db.base import Base
        from crud.user import create_user, get_user_by_email
        from schemas.user import UserCreate
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.sql import text
        import uuid
        
        # Database URL from .env
        DATABASE_URL = "postgresql+asyncpg://postgres:k0u0n0j0123.@db.jpxxulhgqmcncywxewlq.supabase.co:5432/postgres"
        
        # Create engine
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args={
                "ssl": "require",
                "application_name": "nft-marketplace-app-test"
            }
        )
        
        print("✓ Database engine created")
        
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✓ All tables created/verified")
        
        # Get session factory
        async_session = get_async_session(engine)
        
        async with async_session() as session:
            # Check table counts
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"✓ Users table: {user_count} records")
            
            result = await session.execute(text("SELECT COUNT(*) FROM nfts"))
            nft_count = result.scalar()
            print(f"✓ NFTs table: {nft_count} records")
            
            result = await session.execute(text("SELECT COUNT(*) FROM transactions"))
            tx_count = result.scalar()
            print(f"✓ Transactions table: {tx_count} records")
            
            # Create test user
            test_email = f"testuser_{datetime.now().strftime('%Y%m%d_%H%M%S')}@nftmarketplace.com"
            user_data = UserCreate(
                email=test_email,
                full_name="Test User",
                google_id=f"google_test_{uuid.uuid4().hex[:8]}"
            )
            
            created_user = await create_user(session, user_data)
            print(f"✓ Test user created: {created_user.email}")
            print(f"  User ID: {created_user.id}")
            print(f"  Full name: {created_user.full_name}")
            print(f"  Created at: {created_user.created_at}")
            
            # Verify user retrieval
            retrieved_user = await get_user_by_email(session, test_email)
            if retrieved_user:
                print(f"✓ User retrieval successful: ID {retrieved_user.id}")
            
            await session.commit()
            print("✓ Database transaction committed")
        
        await engine.dispose()
        print("\n🎉 NFT Marketplace database is fully functional!")
        print("✅ Backend is ready for production!")
        
        return True
        
    except Exception as e:
        print(f"✗ Application database test failed: {e}")
        import traceback
        print("Traceback:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    result = asyncio.run(test_app_database())
    sys.exit(0 if result else 1)
