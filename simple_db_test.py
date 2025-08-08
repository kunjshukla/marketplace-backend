#!/usr/bin/env python3

import os
import sys
import asyncio
import logging

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("🚀 Starting simple database test...")
logger.info("Logger is working")

try:
    from config.settings import settings
    logger.info("✅ Settings imported successfully")
    print(f"Database URL prefix: {settings.DATABASE_URL[:30]}...")
except Exception as e:
    logger.error(f"❌ Failed to import settings: {e}")
    sys.exit(1)

try:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    logger.info("✅ SQLAlchemy imports successful")
except Exception as e:
    logger.error(f"❌ Failed to import SQLAlchemy: {e}")
    sys.exit(1)

async def simple_db_test():
    logger.info("🧪 Creating database engine...")
    
    try:
        # Convert postgresql:// to postgresql+asyncpg:// for async operations
        async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        logger.info(f"Using async URL: {async_url[:50]}...")
        
        engine = create_async_engine(async_url, echo=False)
        logger.info("✅ Engine created")
        
        logger.info("🔍 Testing connection...")
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            logger.info(f"✅ Query result: {test_value}")
        
        await engine.dispose()
        logger.info("✅ Engine disposed")
        
        return True
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False

if __name__ == "__main__":
    print("🏃 Running async test...")
    try:
        success = asyncio.run(simple_db_test())
        if success:
            print("🎉 Simple database test passed!")
        else:
            print("❌ Simple database test failed!")
    except Exception as e:
        print(f"❌ Error running async test: {e}")
        logger.error(f"❌ Error running async test: {e}")
