from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import settings

# Create SQLAlchemy engine
if settings.DATABASE_URL:
    # Supabase PostgreSQL connection
    engine = create_engine(
        settings.DATABASE_URL,
        echo=True if settings.LOG_LEVEL == "DEBUG" else False,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "sslmode": "require"  # Supabase requires SSL
        } if "postgresql" in settings.DATABASE_URL else {}
    )
else:
    # Fallback for local development
    engine = create_engine(
        "sqlite:///./dev.db",
        connect_args={"check_same_thread": False}
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
