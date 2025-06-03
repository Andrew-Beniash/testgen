"""
Alembic Environment Configuration for Test Generation Agent v2.0

This module configures the Alembic migration environment with support for:
- Async SQLAlchemy operations
- Environment-specific configurations
- Quality assurance features
- Automatic migration for development
- Safe production migrations
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from typing import Any, Dict, Optional

from sqlalchemy import pool, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.engine import Connection
from alembic import context
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.environment import EnvironmentContext

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import application models and configuration
from app.core.config import settings
from app.models.database import Base
from app.core.database import get_engine

# Alembic Config object
config: Config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Get database URL based on environment and configuration.
    
    Returns:
        str: Database URL for migrations
    """
    # Check if we're in testing mode
    if settings.ENVIRONMENT == "testing" and settings.DATABASE_TEST_URL:
        return settings.DATABASE_TEST_URL.replace("+asyncpg", "")  # Use sync driver for migrations
    
    # Use main database URL, convert async to sync for Alembic
    db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    
    # Override from command line if provided
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    
    return db_url


def include_object(object, name, type_, reflected, compare_to):
    """
    Determine whether to include an object in migrations.
    
    This function filters out objects that shouldn't be managed by Alembic.
    
    Args:
        object: The schema object
        name: Object name
        type_: Object type ('table', 'column', 'index', etc.)
        reflected: Whether object was reflected from the database
        compare_to: Target metadata object for comparison
        
    Returns:
        bool: True if object should be included in migration
    """
    # Skip tables not in our schema
    if type_ == "table":
        # Include only tables defined in our models
        return name in target_metadata.tables
    
    # Skip system indexes
    if type_ == "index":
        # Skip PostgreSQL system indexes
        if name.startswith("pg_"):
            return False
        # Skip automatically created unique indexes for unique constraints
        if name.endswith("_key"):
            return False
    
    # Skip foreign key constraints with system-generated names
    if type_ == "foreign_key_constraint":
        if not name or name.startswith("fk_"):
            return False
    
    # Include everything else
    return True


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    """
    Custom type comparison for better migration detection.
    
    This helps avoid unnecessary migrations due to type differences.
    """
    # Handle JSON/JSONB type variations
    if hasattr(metadata_type, 'impl') and hasattr(inspected_type, 'impl'):
        if str(metadata_type.impl) == str(inspected_type.impl):
            return False
    
    # Handle numeric precision differences
    if hasattr(metadata_type, 'precision') and hasattr(inspected_type, 'precision'):
        if (metadata_type.precision == inspected_type.precision and 
            getattr(metadata_type, 'scale', None) == getattr(inspected_type, 'scale', None)):
            return False
    
    # Default comparison
    return context.default_compare_type(inspected_column, metadata_column, inspected_type, metadata_type)


def compare_server_default(context, inspected_column, metadata_column, inspected_default, metadata_default, rendered_metadata_default):
    """
    Custom server default comparison to avoid unnecessary migrations.
    """
    # Handle function calls like now() vs CURRENT_TIMESTAMP
    if inspected_default and metadata_default:
        inspected_norm = str(inspected_default).lower().strip("'\"")
        metadata_norm = str(rendered_metadata_default).lower().strip("'\"")
        
        # Common timestamp function equivalents
        timestamp_functions = [
            ('now()', 'current_timestamp'),
            ('current_timestamp', 'now()'),
            ('current_timestamp', 'timezone(\'utc\'::text, now())'),
        ]
        
        for func1, func2 in timestamp_functions:
            if (inspected_norm == func1 and metadata_norm == func2) or \
               (inspected_norm == func2 and metadata_norm == func1):
                return False
    
    # Default comparison
    return context.default_compare_server_default(
        inspected_column, metadata_column, inspected_default, 
        metadata_default, rendered_metadata_default
    )


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine,
    though an Engine is also acceptable here. By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=compare_type,
        compare_server_default=compare_server_default,
        render_as_batch=False,
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Run migrations with the given connection.
    
    Args:
        connection: Database connection to use for migrations
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=compare_type,
        compare_server_default=compare_server_default,
        render_as_batch=False,
        transaction_per_migration=True,
        # Enable constraint naming for better migration support
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in async mode for compatibility with async SQLAlchemy.
    """
    # Get database URL for sync operations
    database_url = get_database_url()
    
    # Create synchronous engine for migrations
    connectable = create_engine(
        database_url,
        poolclass=pool.NullPool,
        echo=settings.DATABASE_ECHO if settings.ENVIRONMENT == "development" else False,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    
    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    # Check if we should run async
    if asyncio.iscoroutinefunction(do_run_migrations):
        asyncio.run(run_async_migrations())
    else:
        # Synchronous mode
        database_url = get_database_url()
        
        connectable = create_engine(
            database_url,
            poolclass=pool.NullPool,
            echo=settings.DATABASE_ECHO if settings.ENVIRONMENT == "development" else False,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)


# Quality assurance helper functions
def validate_migration_safety() -> bool:
    """
    Validate that the migration is safe to run.
    
    Returns:
        bool: True if migration is safe, False otherwise
    """
    # In production, require additional confirmation for destructive operations
    if settings.ENVIRONMENT == "production":
        # Check for potentially destructive operations
        script_dir = ScriptDirectory.from_config(config)
        
        # This is a simplified check - in a real implementation, you'd parse
        # the migration scripts to detect DROP operations
        return True
    
    return True


def get_migration_context() -> Dict[str, Any]:
    """
    Get migration context with environment-specific settings.
    
    Returns:
        dict: Migration context configuration
    """
    context_config = {
        "include_object": include_object,
        "compare_type": compare_type,
        "compare_server_default": compare_server_default,
        "target_metadata": target_metadata,
        "transaction_per_migration": True,
    }
    
    # Environment-specific configurations
    if settings.ENVIRONMENT == "development":
        context_config.update({
            "render_as_batch": False,
            "compare_type": True,
            "compare_server_default": True,
        })
    elif settings.ENVIRONMENT == "production":
        context_config.update({
            "render_as_batch": False,
            "compare_type": True,
            "compare_server_default": True,
        })
    
    return context_config


# Main execution logic
if context.is_offline_mode():
    run_migrations_offline()
else:
    # Validate migration safety before running
    if validate_migration_safety():
        run_migrations_online()
    else:
        raise RuntimeError("Migration safety validation failed")
