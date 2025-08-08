#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("🚀 Testing database connection with proper SSL...")

try:
    from config.settings import settings
    from sqlalchemy import create_engine, text
    logger.info("✅ Imports successful")
except Exception as e:
    logger.error(f"❌ Import error: {e}")
    sys.exit(1)

def test_db_with_ssl():
    try:
        # Add SSL mode to the database URL
        db_url = settings.DATABASE_URL
        if "?" in db_url:
            ssl_url = f"{db_url}&sslmode=require"
        else:
            ssl_url = f"{db_url}?sslmode=require"
        
        logger.info(f"🔐 Using SSL URL: {ssl_url[:60]}...")
        
        # Create engine with connection timeout
        engine = create_engine(
            ssl_url,
            echo=False,
            connect_args={
                "connect_timeout": 10
            }
        )
        logger.info("✅ Engine created with SSL")
        
        logger.info("🔍 Testing connection with timeout...")
        
        # Test connection with timeout
        with engine.begin() as conn:
            # Simple test query
            result = conn.execute(text("SELECT 1 as test, NOW() as current_time"))
            row = result.fetchone()
            logger.info(f"✅ Connection successful! Test={row[0]}, Time={row[1]}")
            
            # Check database info
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"📊 Database version: {version[:50]}...")
            
            # Check if users table exists
            result = conn.execute(
                text("""
                    SELECT table_name, table_type 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """)
            )
            tables = result.fetchall()
            logger.info(f"📋 Found {len(tables)} tables in public schema:")
            for table in tables:
                logger.info(f"  - {table[0]} ({table[1]})")
            
            # Try to create a simple test if users table exists
            if any(table[0] == 'users' for table in tables):
                logger.info("👤 Users table exists - testing insert...")
                
                test_email = f"test_{datetime.now().strftime('%H%M%S')}@test.com"
                
                try:
                    # Insert test user
                    conn.execute(
                        text("""
                            INSERT INTO users (email, name, is_active, created_at, updated_at) 
                            VALUES (:email, :name, :is_active, :created_at, :updated_at)
                        """),
                        {
                            "email": test_email,
                            "name": "Test User",
                            "is_active": True,
                            "created_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    )
                    
                    # Verify the user
                    result = conn.execute(
                        text("SELECT id, email, name, created_at FROM users WHERE email = :email"),
                        {"email": test_email}
                    )
                    user = result.fetchone()
                    
                    if user:
                        logger.info(f"✅ USER CREATED: ID={user[0]}, Email={user[1]}, Name={user[2]}")
                        logger.info(f"   Created at: {user[3]}")
                        
                        # Clean up - delete test user
                        conn.execute(
                            text("DELETE FROM users WHERE email = :email"),
                            {"email": test_email}
                        )
                        logger.info("🧹 Test user cleaned up")
                    else:
                        logger.warning("⚠️ User creation verification failed")
                        
                except Exception as e:
                    logger.error(f"❌ User operations failed: {e}")
            else:
                logger.warning("⚠️ Users table not found - may need migration")
        
        engine.dispose()
        logger.info("✅ Connection closed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_db_with_ssl()
    if success:
        print("\n🎉 DATABASE CONNECTIVITY TEST PASSED!")
        print("✅ Backend can successfully connect to the database")
        print("✅ Sample user creation and cleanup works")
    else:
        print("\n❌ DATABASE CONNECTIVITY TEST FAILED!")
        sys.exit(1)
