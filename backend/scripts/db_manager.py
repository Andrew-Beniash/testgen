#!/usr/bin/env python3
"""
Database management script for the Test Generation Agent.

This script provides utilities for database operations including
initialization, health checks, migrations, and cleanup.
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Optional
import click
import structlog

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import (
    init_database, 
    close_db_connection,
    test_database_connection,
    create_db_and_tables
)
from app.core.database_test import (
    create_test_database,
    drop_test_database,
    cleanup_test_database,
    verify_test_database_setup,
    test_database_migrations
)
from app.utils.database_health import (
    detailed_health_check,
    cleanup_old_health_logs,
    log_health_status
)
from app.core.config import settings

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def init_db():
    """Initialize the database with tables and initial data."""
    try:
        click.echo("Initializing database...")
        await init_database()
        click.echo("✅ Database initialized successfully!")
        
    except Exception as e:
        click.echo(f"❌ Database initialization failed: {e}")
        sys.exit(1)
    finally:
        await close_db_connection()


async def check_health():
    """Check database health and connectivity."""
    try:
        click.echo("Checking database health...")
        
        # Basic connection test
        connection_info = await test_database_connection()
        
        if connection_info["status"] == "healthy":
            click.echo("✅ Database connection: Healthy")
            click.echo(f"   Database: {connection_info['database_name']}")
            click.echo(f"   User: {connection_info['user_name']}")
            click.echo(f"   Size: {connection_info['database_size_bytes']} bytes")
            click.echo(f"   Tables: {connection_info['table_count']}")
        else:
            click.echo("❌ Database connection: Unhealthy")
            click.echo(f"   Error: {connection_info.get('error', 'Unknown error')}")
            
        # Detailed health check
        click.echo("\nDetailed health check...")
        detailed_health = await detailed_health_check()
        
        if detailed_health["status"] == "healthy":
            click.echo("✅ Detailed health check: Passed")
            
            # Performance metrics
            perf = detailed_health.get("performance", {})
            if perf and "error" not in perf:
                click.echo(f"   Active connections: {perf.get('active_connections', 0)}")
                click.echo(f"   Connection usage: {perf.get('connection_usage_percent', 0):.1f}%")
                click.echo(f"   Database size: {perf.get('database_size_mb', 0):.1f} MB")
            
            # Schema info
            schema = detailed_health.get("schema", {})
            if schema and "error" not in schema:
                click.echo(f"   Schema healthy: {schema.get('schema_healthy', False)}")
                click.echo(f"   Missing tables: {schema.get('missing_tables', [])}")
        else:
            click.echo("❌ Detailed health check: Failed")
            
    except Exception as e:
        click.echo(f"❌ Health check failed: {e}")
        sys.exit(1)
    finally:
        await close_db_connection()


async def setup_test_db():
    """Set up test database."""
    try:
        click.echo("Setting up test database...")
        await create_test_database()
        
        click.echo("Verifying test database setup...")
        is_ready = await verify_test_database_setup()
        
        if is_ready:
            click.echo("✅ Test database setup completed successfully!")
        else:
            click.echo("❌ Test database setup verification failed!")
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Test database setup failed: {e}")
        sys.exit(1)


async def cleanup_test_db():
    """Clean up test database."""
    try:
        click.echo("Cleaning up test database...")
        await cleanup_test_database()
        click.echo("✅ Test database cleaned up successfully!")
        
    except Exception as e:
        click.echo(f"❌ Test database cleanup failed: {e}")
        sys.exit(1)


async def drop_test_db():
    """Drop test database tables."""
    try:
        click.echo("Dropping test database tables...")
        await drop_test_database()
        click.echo("✅ Test database tables dropped successfully!")
        
    except Exception as e:
        click.echo(f"❌ Test database drop failed: {e}")
        sys.exit(1)


async def test_migrations():
    """Test database migrations."""
    try:
        click.echo("Testing database migrations...")
        await test_database_migrations()
        click.echo("✅ Database migrations test passed!")
        
    except Exception as e:
        click.echo(f"❌ Database migrations test failed: {e}")
        sys.exit(1)
    finally:
        await close_db_connection()


async def cleanup_health_logs(days: int):
    """Clean up old health logs."""
    try:
        click.echo(f"Cleaning up health logs older than {days} days...")
        await cleanup_old_health_logs(days)
        click.echo("✅ Health logs cleaned up successfully!")
        
    except Exception as e:
        click.echo(f"❌ Health logs cleanup failed: {e}")
        sys.exit(1)
    finally:
        await close_db_connection()


async def reset_db():
    """Reset database (drop and recreate all tables)."""
    try:
        if not click.confirm("This will drop and recreate all database tables. Continue?"):
            click.echo("Operation cancelled.")
            return
            
        click.echo("Resetting database...")
        
        # Import Base after ensuring path is set
        from app.core.database import Base, get_engine
        
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            click.echo("Tables dropped.")
            
            await conn.run_sync(Base.metadata.create_all)
            click.echo("Tables created.")
        
        # Log the reset
        await log_health_status(
            component="database_reset",
            status="completed",
            message="Database reset completed successfully"
        )
        
        click.echo("✅ Database reset completed successfully!")
        
    except Exception as e:
        click.echo(f"❌ Database reset failed: {e}")
        sys.exit(1)
    finally:
        await close_db_connection()


async def show_info():
    """Display database configuration information."""
    try:
        click.echo("Database Configuration Information:")
        click.echo(f"Environment: {settings.ENVIRONMENT}")
        click.echo(f"Database URL: {settings.DATABASE_URL.split('@')[-1]}")  # Hide credentials
        click.echo(f"Pool Size: {settings.DATABASE_POOL_SIZE}")
        click.echo(f"Max Overflow: {settings.DATABASE_MAX_OVERFLOW}")
        click.echo(f"Echo: {settings.DATABASE_ECHO}")
        
        if settings.DATABASE_TEST_URL:
            click.echo(f"Test Database URL: {settings.DATABASE_TEST_URL.split('@')[-1]}")
        
        # Test connection
        connection_info = await test_database_connection()
        if connection_info["status"] == "healthy":
            click.echo(f"\nDatabase Name: {connection_info['database_name']}")
            click.echo(f"User: {connection_info['user_name']}")
            click.echo(f"PostgreSQL Version: {connection_info['postgresql_version']}")
            click.echo(f"Size: {connection_info.get('database_size_bytes', 0)} bytes")
            click.echo(f"Tables: {connection_info.get('table_count', 0)}")
        
    except Exception as e:
        click.echo(f"❌ Failed to get database info: {e}")
        sys.exit(1)
    finally:
        await close_db_connection()


# CLI Commands
@click.group()
def cli():
    """Database management utilities for Test Generation Agent."""
    pass


@cli.command("init")
def init_cmd():
    """Initialize the database with tables and initial data."""
    asyncio.run(init_db())


@cli.command("health")
def health_cmd():
    """Check database health and connectivity."""
    asyncio.run(check_health())


@cli.command("test-setup")
def test_setup_cmd():
    """Set up test database."""
    asyncio.run(setup_test_db())


@cli.command("test-cleanup")
def test_cleanup_cmd():
    """Clean up test database."""
    asyncio.run(cleanup_test_db())


@cli.command("test-drop")
def test_drop_cmd():
    """Drop test database tables."""
    asyncio.run(drop_test_db())


@cli.command("migrate")
def migrate_cmd():
    """Test database migrations."""
    asyncio.run(test_migrations())


@cli.command("cleanup-logs")
@click.option('--days', default=7, help='Number of days to keep logs')
def cleanup_logs_cmd(days: int):
    """Clean up old health logs."""
    asyncio.run(cleanup_health_logs(days))


@cli.command("reset")
def reset_cmd():
    """Reset database (drop and recreate all tables)."""
    asyncio.run(reset_db())


@cli.command("info")
def info_cmd():
    """Display database configuration information."""
    asyncio.run(show_info())


if __name__ == "__main__":
    cli()
