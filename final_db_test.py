#!/usr/bin/env python3
"""
Final comprehensive database connectivity test for NFT Marketplace Backend
Tests all aspects: network, SSL, connection, table creation, and user operations
"""

import os
import sys
import asyncio
import socket
import ssl
from datetime import datetime
from typing import Optional

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_network_connectivity():
    """Test basic network connectivity to Supabase"""
    print("1. Testing network connectivity...")
    host = "db.jpxxulhgqmcncywxewlq.supabase.co"
    port = 5432
    
    try:
        sock = socket.create_connection((host, port), timeout=10)
        sock.close()
        print("✓ Network connectivity successful")
        return True
    except Exception as e:
        print(f"✗ Network connectivity failed: {e}")
        return False

def test_ssl_connectivity():
    """Test SSL connectivity to Supabase"""
    print("2. Testing SSL connectivity...")
    host = "db.jpxxulhgqmcncywxewlq.supabase.co"
    port = 5432
    
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                print(f"✓ SSL connection established: {ssock.version()}")
                return True
    except Exception as e:
        print(f"✗ SSL connectivity failed: {e}")
        return False

async def test_asyncpg_connection():
    """Test direct asyncpg connection"""
    print("3. Testing asyncpg connection...")
    
    try:
        import asyncpg
        
        conn = await asyncpg.connect(
            user="postgres",
            password="k0u0n0j0123.",
            database="postgres",
            host="db.jpxxulhgqmcncywxewlq.supabase.co",
            port=5432,
            ssl="require",
            server_settings={"application_name": "nft-marketplace-test"},
            timeout=30
        )
        
        # Test basic query
        result = await conn.fetchval("SELECT version()")
        print(f"✓ AsyncPG connection successful")
        print(f"  PostgreSQL version: {result[:50]}...")
        
        # Test table creation
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id SERIAL PRIMARY KEY,
                name TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        print("✓ Test table created")
        
        # Test insert
        await conn.execute(
            "INSERT INTO test_table (name) VALUES ($1)",
            f"test_{datetime.now().isoformat()}"
        )
        print("✓ Test record inserted")
        
        # Test select
        records = await conn.fetch("SELECT * FROM test_table LIMIT 5")
        print(f"✓ Retrieved {len(records)} test records")
        
        # Cleanup
        await conn.execute("DROP TABLE IF EXISTS test_table")
        print("✓ Test table cleaned up")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"✗ AsyncPG connection failed: {e}")
        return False

async def test_sqlalchemy_async():
    """Test SQLAlchemy async connection"""
    print("4. Testing SQLAlchemy async connection...")
    
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.sql import text
        
        DATABASE_URL = "postgresql+asyncpg://postgres:k0u0n0j0123.@db.jpxxulhgqmcncywxewlq.supabase.co:5432/postgres"
        
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={
                "ssl": "require",
                "application_name": "nft-marketplace-sqlalchemy-test"
            }
        )
        
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✓ SQLAlchemy async connection successful")
            print(f"  PostgreSQL version: {version[:50]}...")
        
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"✗ SQLAlchemy async connection failed: {e}")
        return False

async def test_application_models():
    """Test application models and database setup"""
    print("5. Testing application models...")
    
    try:
        # Import application modules
        from db.session import get_async_session
        from models.user import User
        from models.nft import NFT
        from models.transaction import Transaction
        from db.base import Base
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.sql import text
        
        DATABASE_URL = "postgresql+asyncpg://postgres:k0u0n0j0123.@db.jpxxulhgqmcncywxewlq.supabase.co:5432/postgres"
        
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args={
                "ssl": "require",
                "application_name": "nft-marketplace-models-test"
            }
        )
        
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✓ All application tables created/verified")
        
        # Test session creation
        async_session = get_async_session(engine)
        async with async_session() as session:
            # Test basic query
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"✓ Users table accessible, current count: {user_count}")
            
            result = await session.execute(text("SELECT COUNT(*) FROM nfts"))
            nft_count = result.scalar()
            print(f"✓ NFTs table accessible, current count: {nft_count}")
            
            result = await session.execute(text("SELECT COUNT(*) FROM transactions"))
            tx_count = result.scalar()
            print(f"✓ Transactions table accessible, current count: {tx_count}")
        
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"✗ Application models test failed: {e}")
        return False

async def test_user_crud():
    """Test user CRUD operations"""
    print("6. Testing user CRUD operations...")
    
    try:
        from db.session import get_async_session
        from crud.user import create_user, get_user_by_email
        from schemas.user import UserCreate
        from sqlalchemy.ext.asyncio import create_async_engine
        import uuid
        
        DATABASE_URL = "postgresql+asyncpg://postgres:k0u0n0j0123.@db.jpxxulhgqmcncywxewlq.supabase.co:5432/postgres"
        
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args={
                "ssl": "require",
                "application_name": "nft-marketplace-crud-test"
            }
        )
        
        async_session = get_async_session(engine)
        
        async with async_session() as session:
            # Create test user
            test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
            user_data = UserCreate(
                email=test_email,
                full_name="Test User",
                google_id=f"google_{uuid.uuid4().hex[:8]}"
            )
            
            created_user = await create_user(session, user_data)
            print(f"✓ User created successfully: {created_user.email}")
            
            # Retrieve user
            retrieved_user = await get_user_by_email(session, test_email)
            if retrieved_user:
                print(f"✓ User retrieved successfully: {retrieved_user.full_name}")
            else:
                print("✗ User retrieval failed")
                return False
            
            await session.commit()
        
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"✗ User CRUD test failed: {e}")
        return False

async def main():
    """Run all database tests"""
    print("=" * 60)
    print("NFT MARKETPLACE - FINAL DATABASE CONNECTIVITY TEST")
    print("=" * 60)
    print()
    
    tests = [
        ("Network Connectivity", test_network_connectivity),
        ("SSL Connectivity", test_ssl_connectivity),
        ("AsyncPG Connection", test_asyncpg_connection),
        ("SQLAlchemy Async", test_sqlalchemy_async),
        ("Application Models", test_application_models),
        ("User CRUD Operations", test_user_crud),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 40)
        try:
            if asyncio.iscoroutinefunction(test_func):
                success = await test_func()
            else:
                success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
        print()
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    print("-" * 60)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Database is fully functional.")
        print("The NFT Marketplace backend is ready for production!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        print("Database connectivity issues need to be resolved.")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(main())
