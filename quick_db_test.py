#!/usr/bin/env python3

import os
import sys
import logging
import signal
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def timeout_handler(signum, frame):
    raise TimeoutError("Database connection timed out")

def quick_db_test():
    """Quick database connection test with timeout"""
    
    print("🚀 Quick database connection test...")
    
    try:
        from config.settings import settings
        import psycopg2
        from datetime import datetime
        
        # Set a 15-second timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(15)
        
        # Test connection
        db_url = settings.DATABASE_URL
        if '?' not in db_url:
            db_url += '?sslmode=require'
            
        logger.info("🔍 Attempting database connection...")
        
        conn = psycopg2.connect(db_url)
        logger.info("✅ Connected to database!")
        
        cursor = conn.cursor()
        
        # Test 1: Basic query
        cursor.execute("SELECT 1, NOW(), current_database()")
        result = cursor.fetchone()
        logger.info(f"✅ Basic query: {result}")
        
        # Test 2: Check tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        logger.info(f"📋 Found {len(tables)} tables: {[t[0] for t in tables]}")
        
        # Test 3: If users table exists, create a sample user
        table_names = [t[0] for t in tables]
        if 'users' in table_names:
            logger.info("👤 Testing user creation...")
            
            test_email = f"test_user_{datetime.now().strftime('%H%M%S')}@example.com"
            
            try:
                cursor.execute("""
                    INSERT INTO users (email, name, is_active, created_at, updated_at) 
                    VALUES (%s, %s, %s, %s, %s) 
                    RETURNING id, email, name
                """, (
                    test_email,
                    "Test User",
                    True,
                    datetime.utcnow(),
                    datetime.utcnow()
                ))
                
                user = cursor.fetchone()
                conn.commit()
                
                if user:
                    logger.info(f"✅ SAMPLE USER CREATED: ID={user[0]}, Email={user[1]}, Name={user[2]}")
                    
                    # Clean up
                    cursor.execute("DELETE FROM users WHERE email = %s", (test_email,))
                    conn.commit()
                    logger.info("🧹 Test user cleaned up")
                else:
                    logger.warning("⚠️ User creation returned no result")
                    
            except Exception as e:
                logger.error(f"❌ User operations failed: {e}")
                conn.rollback()
        else:
            logger.warning("⚠️ Users table not found")
            # Try to create users table
            logger.info("🔨 Creating users table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255),
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("✅ Users table created!")
        
        cursor.close()
        conn.close()
        signal.alarm(0)  # Cancel timeout
        
        print("\n🎉 DATABASE TEST SUCCESSFUL!")
        print("✅ Connection working")
        print("✅ Basic operations working")
        print("✅ User table ready")
        
        return True
        
    except TimeoutError:
        logger.error("❌ Database connection timed out after 15 seconds")
        return False
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False
    finally:
        signal.alarm(0)  # Make sure to cancel timeout

if __name__ == "__main__":
    success = quick_db_test()
    if success:
        print("✅ Backend database connectivity confirmed!")
        sys.exit(0)
    else:
        print("❌ Backend database connectivity failed!")
        sys.exit(1)
