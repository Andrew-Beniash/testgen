"""
Database testing configuration and utilities.

This module provides testing-specific database configuration,
including test database setup, fixtures, and cleanup utilities.
"""

import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
import pytest
import structlog

from app.core.config import settings
from app.core.database import Base

logger = structlog.get_logger(__name__)

# Test database engine and session factory
_test_engine = None
_test_session_factory = None


def get_test_database_url() -> str:
    """
    Get test database URL.
    
    Returns:
        str: Test database URL
    """
    if settings.DATABASE_TEST_URL:
        return settings.DATABASE_TEST_URL
    
    # Fallback: modify main database URL for testing
    if settings.ENVIRONMENT == "testing":
        base_url = settings.DATABASE_URL
        if "testgen_db" in base_url:
            return base_url.replace("testgen_db", "testgen_test_db")
        else:
            return base_url + "_test"
    
    return settings.DATABASE_URL


def create_test_engine():
    """Create test database engine."""
    global _test_engine
    
    if _test_engine is None:
        test_url = get_test_database_url()
        
        _test_engine = create_async_engine(
            test_url,
            echo=False,  # Disable echo for tests
            pool_size=5,  # Smaller pool for tests
            max_overflow=10,
            pool_pre_ping=True,
            future=True
        )
        
        logger.info("Test database engine created", url=test_url.split("@")[-1])
    
    return _test_engine


def get_test_session_factory():
    """Get test session factory."""
    global _test_session_factory
    
    if _test_session_factory is None:
        _test_session_factory = async_sessionmaker(
            bind=create_test_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    
    return _test_session_factory


@asynccontextmanager
async def get_test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get test database session.
    
    Yields:
        AsyncSession: Test database session
    """
    session_factory = get_test_session_factory()
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_test_database():
    """Create test database and tables."""
    try:
        engine = create_test_engine()
        
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
            # Set up test schema
            await conn.execute(text("SET search_path TO testgen, public"))
            
        logger.info("Test database tables created successfully")
        
    except Exception as e:
        logger.error("Failed to create test database tables", error=str(e))
        raise


async def drop_test_database():
    """Drop all test database tables."""
    try:
        engine = create_test_engine()
        
        async with engine.begin() as conn:
            # Drop all tables
            await conn.run_sync(Base.metadata.drop_all)
            
        logger.info("Test database tables dropped successfully")
        
    except Exception as e:
        logger.error("Failed to drop test database tables", error=str(e))
        raise


async def cleanup_test_database():
    """Clean up test database by truncating all tables."""
    try:
        async with get_test_db_session() as session:
            # Get all table names in testgen schema
            tables_query = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'testgen'
                AND table_type = 'BASE TABLE'
            """)
            
            result = await session.execute(tables_query)
            table_names = [row.table_name for row in result]
            
            # Disable foreign key checks temporarily
            await session.execute(text("SET session_replication_role = replica"))
            
            # Truncate all tables
            for table_name in table_names:
                await session.execute(text(f"TRUNCATE TABLE testgen.{table_name} CASCADE"))
            
            # Re-enable foreign key checks
            await session.execute(text("SET session_replication_role = DEFAULT"))
            
            await session.commit()
            
        logger.info("Test database cleaned up successfully", tables_cleaned=len(table_names))
        
    except Exception as e:
        logger.error("Failed to cleanup test database", error=str(e))
        raise


async def close_test_database():
    """Close test database connections."""
    global _test_engine, _test_session_factory
    
    try:
        if _test_engine:
            await _test_engine.dispose()
            _test_engine = None
            _test_session_factory = None
            logger.info("Test database connection closed successfully")
            
    except Exception as e:
        logger.error("Error closing test database connection", error=str(e))


# Test database fixtures for pytest
@pytest.fixture(scope="session")
async def test_db_engine():
    """Test database engine fixture."""
    engine = create_test_engine()
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def test_db_setup():
    """Set up test database."""
    await create_test_database()
    yield
    await drop_test_database()
    await close_test_database()


@pytest.fixture
async def test_db_session(test_db_setup):
    """Test database session fixture."""
    async with get_test_db_session() as session:
        yield session


@pytest.fixture(autouse=True)
async def cleanup_after_test(test_db_setup):
    """Clean up test database after each test."""
    yield
    await cleanup_test_database()


# Database testing utilities
async def insert_test_data(session: AsyncSession, table_name: str, data: dict):
    """
    Insert test data into a table.
    
    Args:
        session: Database session
        table_name: Name of the table
        data: Data to insert
    """
    try:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{key}" for key in data.keys())
        
        query = text(f"""
            INSERT INTO testgen.{table_name} ({columns})
            VALUES ({placeholders})
            RETURNING id
        """)
        
        result = await session.execute(query, data)
        return result.scalar()
        
    except Exception as e:
        logger.error("Failed to insert test data", table=table_name, error=str(e))
        raise


async def count_table_rows(session: AsyncSession, table_name: str) -> int:
    """
    Count rows in a table.
    
    Args:
        session: Database session
        table_name: Name of the table
        
    Returns:
        int: Number of rows
    """
    try:
        query = text(f"SELECT count(*) FROM testgen.{table_name}")
        result = await session.execute(query)
        return result.scalar()
        
    except Exception as e:
        logger.error("Failed to count table rows", table=table_name, error=str(e))
        raise


async def verify_test_database_setup() -> bool:
    """
    Verify test database is properly set up.
    
    Returns:
        bool: True if test database is ready
    """
    try:
        async with get_test_db_session() as session:
            # Test basic connectivity
            await session.execute(text("SELECT 1"))
            
            # Check if required tables exist
            tables_query = text("""
                SELECT count(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'testgen'
            """)
            
            result = await session.execute(tables_query)
            table_count = result.scalar()
            
            if table_count < 5:  # Should have at least core tables
                logger.warning("Test database has insufficient tables", count=table_count)
                return False
            
            logger.info("Test database setup verified", table_count=table_count)
            return True
            
    except Exception as e:
        logger.error("Test database setup verification failed", error=str(e))
        return False


# Test data factories
class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_user_story_data(**overrides) -> dict:
        """Create user story test data."""
        default_data = {
            "azure_devops_id": "TEST-001",
            "title": "As a user, I want to test functionality",
            "description": "Test user story description",
            "acceptance_criteria": "Given... When... Then...",
            "complexity_score": 0.5,
            "domain_classification": "testing",
            "processing_status": "pending"
        }
        default_data.update(overrides)
        return default_data
    
    @staticmethod
    def create_test_case_data(user_story_id: int, **overrides) -> dict:
        """Create test case test data."""
        default_data = {
            "user_story_id": user_story_id,
            "title": "Test case title",
            "description": "Test case description",
            "steps": [
                {
                    "step_number": 1,
                    "action": "Perform test action",
                    "expected_result": "Expected test result"
                }
            ],
            "classification": "manual",
            "classification_confidence": 0.8,
            "estimated_duration": 5
        }
        default_data.update(overrides)
        return default_data
    
    @staticmethod
    def create_quality_metrics_data(test_case_id: int, **overrides) -> dict:
        """Create quality metrics test data."""
        default_data = {
            "test_case_id": test_case_id,
            "overall_score": 0.8,
            "clarity_score": 0.8,
            "completeness_score": 0.8,
            "executability_score": 0.8,
            "traceability_score": 0.8,
            "realism_score": 0.8,
            "coverage_score": 0.8,
            "confidence_level": "high",
            "validation_passed": True
        }
        default_data.update(overrides)
        return default_data


# Performance testing utilities
async def measure_query_performance(session: AsyncSession, query: str, params: dict = None) -> dict:
    """
    Measure query performance.
    
    Args:
        session: Database session
        query: SQL query to measure
        params: Query parameters
        
    Returns:
        dict: Performance metrics
    """
    import time
    
    try:
        start_time = time.time()
        
        result = await session.execute(text(query), params or {})
        rows = result.fetchall()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        return {
            "execution_time_seconds": execution_time,
            "row_count": len(rows),
            "query": query,
            "performance_ok": execution_time < 1.0  # 1 second threshold
        }
        
    except Exception as e:
        logger.error("Query performance measurement failed", error=str(e))
        raise


# Migration testing utilities
async def test_database_migrations():
    """Test database migrations and schema consistency."""
    try:
        async with get_test_db_session() as session:
            # Test that all expected tables exist
            expected_tables = [
                "user_stories", "test_cases", "quality_metrics",
                "qa_annotations", "learning_contributions",
                "ground_truth_benchmark", "system_health_log",
                "generation_statistics"
            ]
            
            for table in expected_tables:
                count_query = text(f"""
                    SELECT count(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'testgen' 
                    AND table_name = :table_name
                """)
                
                result = await session.execute(count_query, {"table_name": table})
                exists = result.scalar() > 0
                
                if not exists:
                    raise AssertionError(f"Expected table {table} does not exist")
            
            logger.info("Database migration test passed", tables_verified=len(expected_tables))
            return True
            
    except Exception as e:
        logger.error("Database migration test failed", error=str(e))
        raise
