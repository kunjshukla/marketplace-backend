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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("🚀 Starting synchronous database test...")

try:
    from config.settings import settings
    logger.info("✅ Settings imported successfully")
except Exception as e:
    logger.error(f"❌ Failed to import settings: {e}")
    sys.exit(1)

try:
    from sqlalchemy import create_engine, text
    logger.info("✅ SQLAlchemy imports successful")
except Exception as e:
    logger.error(f"❌ Failed to import SQLAlchemy: {e}")
    sys.exit(1)

def sync_db_test():
    logger.info("🧪 Creating synchronous database engine...")
    
    try:
        # Use regular postgresql:// for sync operations
        engine = create_engine(settings.DATABASE_URL, echo=False)
        logger.info("✅ Engine created")
        
        logger.info("🔍 Testing connection...")
        with engine.begin() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            logger.info(f"✅ Query result: {test_value}")
        
        # Test 2: Check if users table exists
        logger.info("\n2️⃣ Checking users table...")
        with engine.begin() as conn:
            result = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users')")
            )
            table_exists = result.scalar()
            if table_exists:
                logger.info("✅ Users table exists!")
                
                # Count users
                result = conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()
                logger.info(f"📊 Found {user_count} existing users")
                
                # Create sample user
                test_email = f"test_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"
                logger.info(f"📝 Creating user: {test_email}")
                
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
                logger.info("✅ Sample user created!")
                
                # Verify user
                result = conn.execute(
                    text("SELECT id, email, name FROM users WHERE email = :email"),
                    {"email": test_email}
                )
                user_row = result.fetchone()
                if user_row:
                    logger.info(f"✅ User verified: ID={user_row[0]}, Email={user_row[1]}, Name={user_row[2]}")
                
            else:
                logger.warning("⚠️ Users table doesn't exist - may need migration")
        
        engine.dispose()
        logger.info("✅ Engine disposed")
        
        return True
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False

if __name__ == "__main__":
    print("🏃 Running sync test...")
    try:
        success = sync_db_test()
        if success:
            print("🎉 Synchronous database test passed!")
        else:
            print("❌ Synchronous database test failed!")
    except Exception as e:
        print(f"❌ Error running sync test: {e}")
        logger.error(f"❌ Error running sync test: {e}")
