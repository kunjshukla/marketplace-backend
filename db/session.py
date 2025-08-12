from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.engine.url import make_url
from config.settings import settings
from db.base import Base
import logging
import socket

logger = logging.getLogger(__name__)

# Build sync engine with IPv4 preference for Supabase
try:
    url = make_url(settings.DATABASE_URL_SYNC)
except Exception:
    # Fallback to raw string
    url = settings.DATABASE_URL_SYNC  # type: ignore

engine_kwargs = {"pool_pre_ping": True, "pool_recycle": 300}

def _make_sync_engine():
    # SQLite
    if isinstance(url, str):
        return create_engine(url, **engine_kwargs)
    if url.drivername.startswith("sqlite"):
        return create_engine(str(url), connect_args={"check_same_thread": False}, **engine_kwargs)

    # Postgres with psycopg2: resolve IPv4 to avoid IPv6 issues inside containers
    if url.drivername.startswith("postgresql") and url.host:
        try:
            infos = socket.getaddrinfo(url.host, url.port or 5432, family=socket.AF_INET, type=socket.SOCK_STREAM)
            ipv4 = infos[0][4][0] if infos else None
        except Exception as e:
            logger.warning(f"IPv4 DNS resolution failed for {url.host}: {e}")
            ipv4 = None
        if ipv4:
            try:
                import psycopg2  # type: ignore
                def _creator():
                    return psycopg2.connect(
                        host=ipv4,
                        port=url.port or 5432,
                        user=url.username,
                        password=url.password,
                        dbname=url.database,
                        sslmode=(url.query.get("sslmode", "require") if hasattr(url, "query") else "require"),
                        connect_timeout=10,
                        application_name="nft-marketplace-backend",
                    )
                return create_engine(str(url), creator=_creator, **engine_kwargs)
            except Exception as e:
                logger.warning(f"IPv4 creator connect fallback: {e}")
        # Default engine
        return create_engine(str(url), **engine_kwargs)

    # Default
    return create_engine(str(url), **engine_kwargs)

# Sync engine for compatibility
engine = _make_sync_engine()

# Async engine (optional)
try:
    if settings.DATABASE_URL_ASYNC.startswith("postgresql+asyncpg://"):
        async_engine = create_async_engine(
            settings.DATABASE_URL_ASYNC,
            echo=False,
            pool_pre_ping=True,
        )
    else:
        async_engine = None
except Exception as e:
    logger.warning(f"Async engine unavailable: {e}")
    async_engine = None

# Create sessionmakers
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if async_engine:
    AsyncSessionLocal = sessionmaker(class_=AsyncSession, autocommit=False, autoflush=False, bind=async_engine)
else:
    AsyncSessionLocal = None

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def get_async_session(engine=None):
    """Get async session factory"""
    if engine and async_engine:
        return sessionmaker(class_=AsyncSession, bind=async_engine)
    return AsyncSessionLocal

async def get_async_db():
    """Dependency to get async database session"""
    if not AsyncSessionLocal:
        raise RuntimeError("Async engine not configured for current database URL")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Async database error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

async def create_tables_async():
    """Create all tables async"""
    if not async_engine:
        raise RuntimeError("Async engine not configured")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
