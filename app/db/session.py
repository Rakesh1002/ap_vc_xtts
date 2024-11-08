from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool
from app.core.config import get_settings
import logging
from app.db.base import Base
from typing import AsyncGenerator
from app.core.metrics import DB_CONNECTIONS, DB_OPERATION_LATENCY
import time

logger = logging.getLogger(__name__)
settings = get_settings()

# Create async engine with connection pooling
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DB_ECHO,
    echo_pool=settings.DB_ECHO_POOL,
    pool_pre_ping=settings.DB_PRE_PING,
    poolclass=AsyncAdaptedQueuePool,  # Use async pool
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_reset_on_return=settings.DB_POOL_RESET_ON_RETURN,
    connect_args={
        "timeout": settings.DB_POOL_TIMEOUT,
        "command_timeout": settings.DB_POOL_TIMEOUT
    }
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session from pool"""
    start_time = time.time()
    DB_CONNECTIONS.labels(state="active").inc()
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            duration = time.time() - start_time
            DB_OPERATION_LATENCY.labels(operation="session").observe(duration)
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            DB_CONNECTIONS.labels(state="error").inc()
            raise
            
        finally:
            await session.close()
            DB_CONNECTIONS.labels(state="active").dec()

async def init_db_pool():
    """Initialize database connection pool"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        # Log pool statistics
        pool = engine.pool
        logger.info(
            f"Database pool initialized: "
            f"size={pool.size()}, "
            f"overflow={pool.overflow()}"
        )
        
        # Update metrics
        DB_CONNECTIONS.labels(state="pool_size").set(pool.size())
        DB_CONNECTIONS.labels(state="pool_overflow").set(pool.overflow())
        
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        raise

async def close_db_pool():
    """Close database connection pool"""
    try:
        await engine.dispose()
        logger.info("Database pool closed")
        
        # Update metrics
        DB_CONNECTIONS.labels(state="pool_size").set(0)
        DB_CONNECTIONS.labels(state="pool_overflow").set(0)
        
    except Exception as e:
        logger.error(f"Error closing database pool: {e}")
        raise

# Create sync engine for Celery tasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sync_engine = create_engine(
    settings.sync_database_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)