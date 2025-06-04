"""
Redis connection manager for the Test Generation Agent.

This module provides a connection pool for Redis and utility functions
for working with Redis including connection management, error handling,
and automatic reconnection.
"""

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.retry import Retry
from redis.exceptions import RedisError
import structlog
from typing import Optional, Any, Dict, List, Union, Set
import json
import time
import asyncio

from app.core.config import settings
from app.utils.correlation import get_correlation_logger

# Set up logger with correlation tracking
logger = get_correlation_logger(__name__)

# Redis connection pool
_redis_pool: Optional[ConnectionPool] = None


async def get_redis_pool() -> ConnectionPool:
    """
    Get the Redis connection pool with lazy initialization.
    
    Returns:
        ConnectionPool: The Redis connection pool.
    """
    global _redis_pool
    
    if _redis_pool is None:
        logger.info(
            "Initializing Redis connection pool",
            redis_url=settings.REDIS_URL.replace(
                # Mask password in logs if present
                "://:" + settings.REDIS_URL.split("://:", 1)[1].split("@", 1)[0] if "://:" in settings.REDIS_URL else "",
                "://:***"
            )
        )
        
        retry_strategy = Retry(
            retries=3,
            backoff=1,
            backoff_factor=2.0,
            retry_on_error=[RedisError]
        )
        
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            retry_on_timeout=True,
            retry=retry_strategy,
            max_connections=50
        )
    
    return _redis_pool


async def get_redis_client() -> redis.Redis:
    """
    Get a Redis client from the connection pool.
    
    Returns:
        redis.Redis: A Redis client connected to the pool.
    """
    pool = await get_redis_pool()
    return redis.Redis(connection_pool=pool)


async def close_redis_connections():
    """Close all Redis connections in the pool."""
    global _redis_pool
    
    if _redis_pool:
        logger.info("Closing Redis connection pool")
        await _redis_pool.disconnect()
        _redis_pool = None


async def ping_redis() -> bool:
    """
    Ping Redis to check if it's alive.
    
    Returns:
        bool: True if Redis responded to ping, False otherwise.
    """
    try:
        async with (await get_redis_client()) as client:
            await client.ping()
            return True
    except RedisError as e:
        logger.error(
            "Redis ping failed",
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def get_redis_info() -> Dict[str, Any]:
    """
    Get Redis server information.
    
    Returns:
        Dict[str, Any]: Redis server information.
    """
    try:
        async with (await get_redis_client()) as client:
            info = await client.info()
            return info
    except RedisError as e:
        logger.error(
            "Failed to get Redis info",
            error=str(e),
            error_type=type(e).__name__
        )
        return {"error": str(e)}
