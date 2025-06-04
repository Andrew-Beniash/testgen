"""
Database configuration and session management.

This module sets up the database connection, session management,
and provides the database dependency for FastAPI with enhanced
connection pooling, health checks, and error handling.
"""

import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    create_async_engine, 
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Create declarative base for models
Base = declarative_base()

# Global engine instance
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker] = None


def create_database_engine() -> AsyncEngine:
    """
    Create database engine with proper configuration.
    
    Returns:
        AsyncEngine: Configured database engine
    """
    # Choose pool class based on environment
    if settings.ENVIRONMENT == "testing":
        pool_class = NullPool
        pool_kwargs = {}
    else:
        pool_class = QueuePool
        pool_kwargs = {
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "pool_pre_ping": True,  # Validate connections before use
            "pool_recycle": 3600,   # Recycle connections every hour
        }
    
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool_class,
        echo=settings.DATABASE_ECHO,
        future=True,
        **pool_kwargs
    )
    
    logger.info(
        "Database engine created",
        url=settings.DATABASE_URL.split("@")[-1],  # Hide credentials
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        environment=settings.ENVIRONMENT
    )
    
    return engine


def get_engine() -> AsyncEngine:
    """Get or create database engine."""
    global _engine
    if _engine is None:
        _engine = create_database_engine()
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Get or create session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session with proper error handling.
    
    Yields:
        AsyncSession: Database session
        
    Raises:
        SQLAlchemyError: If database operation fails
    """
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        try:
            # Test connection at start of session
            await session.execute(text("SELECT 1"))
            yield session
            await session.commit()
            
        except DisconnectionError as e:
            logger.error("Database disconnection error", error=str(e))
            await session.rollback()
            raise
            
        except SQLAlchemyError as e:
            logger.error("Database operation error", error=str(e))
            await session.rollback()
            raise
            
        except Exception as e:
            logger.error("Unexpected database error", error=str(e))
            await session.rollback()
            raise
            
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions outside of FastAPI dependency injection.
    
    Yields:
        AsyncSession: Database session
    """
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> bool:
    """
    Check database connectivity and health.
    
    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        async with get_db_session() as session:
            # Test basic connectivity
            result = await session.execute(text("SELECT 1 as health_check"))
            health_check = result.scalar()
            
            if health_check != 1:
                logger.warning("Database health check returned unexpected value", value=health_check)
                return False
                
            # Test database-specific functionality
            await session.execute(text("SELECT current_database(), current_user"))
            
            logger.debug("Database health check passed")
            return True
            
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False


async def create_db_and_tables() -> None:
    """
    Create database tables and set up initial configuration.
    
    Raises:
        SQLAlchemyError: If table creation fails
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
            # Set up schema and permissions (if needed)
            await conn.execute(text("SET search_path TO testgen, public"))
            
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        raise


async def close_db_connection() -> None:
    """Close database connection and clean up resources."""
    global _engine, _session_factory
    
    try:
        if _engine:
            await _engine.dispose()
            _engine = None
            _session_factory = None
            logger.info("Database connection closed successfully")
            
    except Exception as e:
        logger.error("Error closing database connection", error=str(e))
        raise


async def test_database_connection() -> dict:
    """
    Test database connection and return connection info.
    
    Returns:
        dict: Connection information and test results
    """
    try:
        async with get_db_session() as session:
            # Get database info
            db_info_query = text("""
                SELECT 
                    current_database() as database_name,
                    current_user as user_name,
                    version() as postgresql_version,
                    current_setting('server_version') as server_version,
                    pg_database_size(current_database()) as database_size,
                    (SELECT count(*) FROM information_schema.tables 
                     WHERE table_schema = 'testgen') as table_count
            """)
            
            result = await session.execute(db_info_query)
            row = result.fetchone()
            
            connection_info = {
                "status": "healthy",
                "database_name": row.database_name,
                "user_name": row.user_name,
                "postgresql_version": row.postgresql_version.split(" ")[0] if row.postgresql_version else "unknown",
                "server_version": row.server_version,
                "database_size_bytes": row.database_size,
                "table_count": row.table_count,
                "pool_size": settings.DATABASE_POOL_SIZE,
                "max_overflow": settings.DATABASE_MAX_OVERFLOW
            }
            
            logger.info("Database connection test successful", **connection_info)
            return connection_info
            
    except Exception as e:
        error_info = {
            "status": "unhealthy",
            "error": str(e),
            "error_type": type(e).__name__
        }
        logger.error("Database connection test failed", **error_info)
        return error_info


# Database initialization function for startup
async def init_database():
    """Initialize database connection and validate setup."""
    try:
        # Test connection
        connection_info = await test_database_connection()
        
        if connection_info["status"] != "healthy":
            raise RuntimeError(f"Database initialization failed: {connection_info.get('error')}")
        
        # Create tables if they don't exist
        await create_db_and_tables()
        
        # Run migrations if necessary
        from app.utils.migrations import handle_automatic_migration
        migration_success = await handle_automatic_migration()
        
        if not migration_success and settings.ENVIRONMENT != "production":
            logger.warning("Automatic migration failed - continuing anyway")
        elif not migration_success and settings.ENVIRONMENT == "production":
            raise RuntimeError("Migration failed in production environment")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise


# Retry decorator for database operations
def with_db_retry(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry database operations on connection failures.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except (DisconnectionError, ConnectionError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            "Database operation failed, retrying",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            error=str(e)
                        )
                        await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error(
                            "Database operation failed after all retries",
                            attempts=max_retries + 1,
                            error=str(e)
                        )
                        
                except Exception as e:
                    # Don't retry non-connection errors
                    logger.error("Database operation failed with non-retryable error", error=str(e))
                    raise
                    
            # If we get here, all retries failed
            raise last_exception
            
        return wrapper
    return decorator
