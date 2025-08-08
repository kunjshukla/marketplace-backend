#!/usr/bin/env python3
"""
Test script to check database connectivity and create a sample user
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from db.session import SessionLocal, engine
from db.base import Base
from models.user import User
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_connection():
    """Test basic database connection"""
    try:
        # Test connection
        with engine.connect() as connection:
            logger.info("✅ Database connection successful!")
            result = connection.execute("SELECT 1")
            logger.info(f"✅ Test query result: {result.scalar()}")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

def create_tables():
    """Create all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tables created successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Table creation failed: {e}")
        return False

def create_sample_user():
    """Create a sample user entry"""
    db: Session = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == "test@example.com").first()
        if existing_user:
            logger.info(f"✅ Sample user already exists: {existing_user.email}")
            return existing_user
        
        # Create sample user
        sample_user = User(
            name="Test User",
            email="test@example.com",
            google_id="test_google_id_123",
            profile_pic="https://via.placeholder.com/150",
            role="user",
            is_active=True
        )
        
        db.add(sample_user)
        db.commit()
        db.refresh(sample_user)
        
        logger.info(f"✅ Sample user created successfully!")
        logger.info(f"   ID: {sample_user.id}")
        logger.info(f"   Name: {sample_user.name}")
        logger.info(f"   Email: {sample_user.email}")
        logger.info(f"   Created at: {sample_user.created_at}")
        
        return sample_user
        
    except Exception as e:
        logger.error(f"❌ Failed to create sample user: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def list_users():
    """List all users in the database"""
    db: Session = SessionLocal()
    try:
        users = db.query(User).all()
        logger.info(f"📋 Total users in database: {len(users)}")
        for user in users:
            logger.info(f"   - {user.name} ({user.email}) - ID: {user.id}")
        return users
    except Exception as e:
        logger.error(f"❌ Failed to list users: {e}")
        return []
    finally:
        db.close()

def main():
    """Main test function"""
    logger.info("🧪 Starting database connectivity test...")
    
    # Test 1: Database connection
    logger.info("\n1️⃣ Testing database connection...")
    if not test_database_connection():
        logger.error("❌ Database connection test failed. Exiting.")
        return False
    
    # Test 2: Create tables
    logger.info("\n2️⃣ Creating database tables...")
    if not create_tables():
        logger.error("❌ Table creation failed. Exiting.")
        return False
    
    # Test 3: Create sample user
    logger.info("\n3️⃣ Creating sample user...")
    sample_user = create_sample_user()
    if not sample_user:
        logger.error("❌ Sample user creation failed. Exiting.")
        return False
    
    # Test 4: List all users
    logger.info("\n4️⃣ Listing all users...")
    list_users()
    
    logger.info("\n✅ All database tests completed successfully!")
    logger.info("🎉 Database connectivity confirmed!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
