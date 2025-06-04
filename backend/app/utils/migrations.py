"""
Database migration utilities.

This module provides utilities for running database migrations
programmatically using Alembic.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import structlog
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from alembic import command
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db_session

logger = structlog.get_logger(__name__)


def get_alembic_config() -> Config:
    """
    Get Alembic configuration.
    
    Returns:
        Config: Alembic configuration object
    """
    # Get project root directory
    project_root = Path(__file__).parent.parent.parent
    
    # Create Alembic config
    config = Config(str(project_root / "alembic.ini"))
    
    # Set script location from settings
    config.set_main_option("script_location", settings.ALEMBIC_SCRIPT_LOCATION)
    
    # Set database URL
    if settings.ENVIRONMENT == "testing" and settings.DATABASE_TEST_URL:
        db_url = settings.DATABASE_TEST_URL.replace("+asyncpg", "")  # Use sync driver for Alembic
    else:
        db_url = settings.DATABASE_URL.replace("+asyncpg", "")  # Use sync driver for Alembic
    
    config.set_main_option("sqlalchemy.url", db_url)
    
    # Add environment-specific settings
    config.set_section_option(f"alembic:{settings.ENVIRONMENT}", "compare_type", "true")
    
    return config


async def get_current_revision() -> Optional[str]:
    """
    Get current database revision.
    
    Returns:
        str: Current revision or None if no revision
    """
    try:
        async with get_db_session() as session:
            # Check if alembic_version table exists
            check_query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'testgen' 
                    AND table_name = 'alembic_version'
                )
            """)
            
            result = await session.execute(check_query)
            table_exists = result.scalar()
            
            if not table_exists:
                logger.info("No alembic_version table found - database not initialized")
                return None
            
            # Get current revision
            query = text("SELECT version_num FROM alembic_version")
            result = await session.execute(query)
            revision = result.scalar()
            
            return revision
    except Exception as e:
        logger.error("Failed to get current revision", error=str(e))
        return None


def get_available_migrations() -> List[Dict[str, Any]]:
    """
    Get available migrations.
    
    Returns:
        List[Dict[str, Any]]: List of available migrations
    """
    try:
        config = get_alembic_config()
        script = ScriptDirectory.from_config(config)
        
        migrations = []
        for sc in script.walk_revisions():
            migrations.append({
                "revision": sc.revision,
                "down_revision": sc.down_revision,
                "doc": sc.doc,
                "branch_labels": sc.branch_labels,
                "is_head": sc.is_head,
                "is_branch_point": sc.is_branch_point,
                "is_merge_point": sc.is_merge_point
            })
        
        return migrations
    except Exception as e:
        logger.error("Failed to get available migrations", error=str(e))
        return []


async def run_migrations(target: str = "head") -> bool:
    """
    Run database migrations.
    
    Args:
        target: Target revision
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get configuration
        config = get_alembic_config()
        
        # Check environment constraints
        if settings.ENVIRONMENT == "production" and not target.isdigit():
            # Only allow specific revision upgrades in production
            logger.warning(
                "Automatic migration to non-specific revision is not allowed in production",
                target=target
            )
            return False
        
        # Get current revision for logging
        current = await get_current_revision()
        logger.info("Running database migrations", current=current, target=target)
        
        # Run migrations
        command.upgrade(config, target)
        
        # Get new revision for confirmation
        new_revision = await get_current_revision()
        
        logger.info(
            "Database migrations completed successfully",
            previous=current,
            current=new_revision
        )
        
        return True
    except Exception as e:
        logger.error("Database migration failed", error=str(e))
        return False


async def check_if_migration_needed() -> bool:
    """
    Check if database migration is needed.
    
    Returns:
        bool: True if migration is needed, False otherwise
    """
    try:
        # Get current revision
        current = await get_current_revision()
        
        if current is None:
            logger.info("Database not initialized - migration needed")
            return True
        
        # Get available migrations
        migrations = get_available_migrations()
        
        # Check if current revision is head
        heads = [m["revision"] for m in migrations if m["is_head"]]
        
        if current not in heads:
            logger.info(
                "Database not at head revision - migration needed",
                current=current,
                heads=heads
            )
            return True
        
        logger.info("Database at head revision - no migration needed", current=current)
        return False
    except Exception as e:
        logger.error("Failed to check if migration is needed", error=str(e))
        # Default to True to be safe
        return True


async def handle_automatic_migration() -> bool:
    """
    Handle automatic database migration based on settings.
    
    Returns:
        bool: True if successful or not needed, False if failed
    """
    try:
        # Check if automatic migration is enabled
        if not settings.ALEMBIC_AUTO_MIGRATE:
            logger.info("Automatic migration disabled")
            return True
        
        # Check if we're in development or testing environment
        if settings.ENVIRONMENT not in ["development", "testing"]:
            logger.info(f"Automatic migration not allowed in {settings.ENVIRONMENT} environment")
            return True
        
        # Check if migration is needed
        if not await check_if_migration_needed():
            return True
        
        # Run migrations
        target = settings.ALEMBIC_MIGRATION_TARGET
        success = await run_migrations(target)
        
        return success
    except Exception as e:
        logger.error("Automatic migration failed", error=str(e))
        return False
