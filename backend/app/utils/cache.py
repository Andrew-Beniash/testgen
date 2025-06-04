"""
Redis caching utilities for the Test Generation Agent.

This module provides utilities for caching data in Redis,
including automatic serialization/deserialization of objects,
pattern-based cache invalidation, and cache statistics.
"""

import json
import hashlib
import time
import asyncio
from functools import wraps
from typing import Any, Dict, List, Optional, Callable, Set, Union, Tuple, TypeVar, cast
from redis.asyncio import Redis
from redis.exceptions import RedisError
import structlog
import inspect
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.redis import get_redis_client
from app.utils.correlation import get_correlation_logger

# Set up logger with correlation tracking
logger = get_correlation_logger(__name__)

# Type variables for generic cache functions
T = TypeVar('T')
CacheableResult = TypeVar('CacheableResult')

# Cache statistics keys
CACHE_HITS_KEY = "testgen:cache:stats:hits"
CACHE_MISSES_KEY = "testgen:cache:stats:misses"
CACHE_ERRORS_KEY = "testgen:cache:stats:errors"


async def cache_get(key: str, default: Any = None) -> Any:
    """
    Get a value from cache with error handling.
    
    Args:
        key: The cache key
        default: Default value if key doesn't exist
        
    Returns:
        The cached value or default
    """
    try:
        async with (await get_redis_client()) as client:
            cached_value = await client.get(key)
            
            if cached_value:
                await client.hincrby(CACHE_HITS_KEY, key, 1)
                return json.loads(cached_value)
            else:
                await client.hincrby(CACHE_MISSES_KEY, key, 1)
                return default
    except RedisError as e:
        await increment_cache_error(key, str(e))
        logger.warning(
            "Cache get error",
            key=key,
            error=str(e),
            error_type=type(e).__name__
        )
        return default


async def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """
    Set a value in cache with error handling.
    
    Args:
        key: The cache key
        value: The value to cache (will be JSON serialized)
        ttl: Time-to-live in seconds (None for default from settings)
        
    Returns:
        True if successful, False otherwise
    """
    if ttl is None:
        ttl = settings.REDIS_CACHE_TTL
        
    try:
        async with (await get_redis_client()) as client:
            json_value = json.dumps(value)
            await client.set(key, json_value, ex=ttl)
            return True
    except (RedisError, TypeError, ValueError) as e:
        await increment_cache_error(key, str(e))
        logger.warning(
            "Cache set error",
            key=key,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def cache_delete(key: str) -> bool:
    """
    Delete a value from cache.
    
    Args:
        key: The cache key
        
    Returns:
        True if key was deleted, False otherwise
    """
    try:
        async with (await get_redis_client()) as client:
            result = await client.delete(key)
            return result > 0
    except RedisError as e:
        await increment_cache_error(key, str(e))
        logger.warning(
            "Cache delete error",
            key=key,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """
    Delete all keys matching a pattern.
    
    Args:
        pattern: The key pattern to match (e.g., "user:*")
        
    Returns:
        Number of keys deleted
    """
    try:
        async with (await get_redis_client()) as client:
            # First, scan for keys matching the pattern
            keys_to_delete = []
            async for key in client.scan_iter(match=pattern):
                keys_to_delete.append(key)
            
            # If there are keys to delete, delete them
            if keys_to_delete:
                deleted = await client.delete(*keys_to_delete)
                logger.info(
                    "Cache keys deleted",
                    pattern=pattern,
                    count=deleted
                )
                return deleted
            return 0
    except RedisError as e:
        await increment_cache_error(pattern, str(e))
        logger.warning(
            "Cache delete pattern error",
            pattern=pattern,
            error=str(e),
            error_type=type(e).__name__
        )
        return 0


async def cache_exists(key: str) -> bool:
    """
    Check if a key exists in the cache.
    
    Args:
        key: The cache key
        
    Returns:
        True if key exists, False otherwise
    """
    try:
        async with (await get_redis_client()) as client:
            return await client.exists(key) > 0
    except RedisError as e:
        await increment_cache_error(key, str(e))
        logger.warning(
            "Cache exists error",
            key=key,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def cache_ttl(key: str) -> Optional[int]:
    """
    Get the remaining time-to-live for a key.
    
    Args:
        key: The cache key
        
    Returns:
        TTL in seconds or None if key doesn't exist or has no expiry
    """
    try:
        async with (await get_redis_client()) as client:
            ttl = await client.ttl(key)
            return None if ttl < 0 else ttl
    except RedisError as e:
        await increment_cache_error(key, str(e))
        logger.warning(
            "Cache TTL error",
            key=key,
            error=str(e),
            error_type=type(e).__name__
        )
        return None


async def cache_extend_ttl(key: str, ttl: int) -> bool:
    """
    Extend the TTL of an existing key.
    
    Args:
        key: The cache key
        ttl: New TTL in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        async with (await get_redis_client()) as client:
            return await client.expire(key, ttl)
    except RedisError as e:
        await increment_cache_error(key, str(e))
        logger.warning(
            "Cache extend TTL error",
            key=key,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def increment_cache_error(key: str, error_message: str):
    """Increment error counter for a specific key."""
    try:
        async with (await get_redis_client()) as client:
            await client.hincrby(CACHE_ERRORS_KEY, key, 1)
    except RedisError:
        # Silently fail - this is just for stats
        pass


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a consistent cache key from prefix and arguments.
    
    Args:
        prefix: Key prefix (typically function or model name)
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        A cache key string
    """
    # Convert args and kwargs to strings
    arg_str = ':'.join(str(arg) for arg in args)
    kwarg_str = ':'.join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    
    # Combine and hash if the key would be too long
    combined = f"{prefix}:{arg_str}:{kwarg_str}"
    if len(combined) > 100:
        # Create a hash for the long part
        hashed = hashlib.md5(combined.encode()).hexdigest()
        return f"{prefix}:{hashed}"
    
    return combined


def cached(
    prefix: str,
    ttl: Optional[int] = None,
    key_builder: Optional[Callable[..., str]] = None
):
    """
    Decorator to cache function results in Redis.
    
    Args:
        prefix: Key prefix for the cache
        ttl: Cache TTL in seconds (None for default)
        key_builder: Optional function to build custom cache keys
    
    Example:
        @cached("user_profile", ttl=3600)
        async def get_user_profile(user_id: int) -> Dict:
            # Expensive operation to get user profile
            return await db.get_user(user_id)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = generate_cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = await cache_get(cache_key)
            if cached_result is not None:
                logger.debug(
                    "Cache hit",
                    function=func.__name__,
                    key=cache_key
                )
                return cached_result
            
            # Cache miss, execute function
            logger.debug(
                "Cache miss",
                function=func.__name__,
                key=cache_key
            )
            result = await func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                await cache_set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


async def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics including hits, misses, and errors.
    
    Returns:
        Dict with cache statistics
    """
    try:
        async with (await get_redis_client()) as client:
            pipeline = client.pipeline()
            pipeline.hgetall(CACHE_HITS_KEY)
            pipeline.hgetall(CACHE_MISSES_KEY)
            pipeline.hgetall(CACHE_ERRORS_KEY)
            pipeline.info("memory")
            pipeline.info("stats")
            
            results = await pipeline.execute()
            
            hits = results[0]
            misses = results[1]
            errors = results[2]
            memory = results[3]
            stats = results[4]
            
            # Calculate totals
            total_hits = sum(int(v) for v in hits.values()) if hits else 0
            total_misses = sum(int(v) for v in misses.values()) if misses else 0
            total_errors = sum(int(v) for v in errors.values()) if errors else 0
            total_requests = total_hits + total_misses
            hit_ratio = total_hits / total_requests if total_requests > 0 else 0
            
            return {
                "summary": {
                    "total_hits": total_hits,
                    "total_misses": total_misses,
                    "total_errors": total_errors,
                    "total_requests": total_requests,
                    "hit_ratio": hit_ratio,
                    "used_memory_human": memory.get("used_memory_human", "unknown"),
                    "used_memory_peak_human": memory.get("used_memory_peak_human", "unknown"),
                    "total_keys": stats.get("keyspace_hits", 0) + stats.get("keyspace_misses", 0)
                },
                "hits_by_key": hits,
                "misses_by_key": misses,
                "errors_by_key": errors
            }
    except RedisError as e:
        logger.error(
            "Failed to get cache stats",
            error=str(e),
            error_type=type(e).__name__
        )
        return {"error": str(e)}


async def reset_cache_stats() -> bool:
    """
    Reset cache statistics.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        async with (await get_redis_client()) as client:
            pipeline = client.pipeline()
            pipeline.delete(CACHE_HITS_KEY)
            pipeline.delete(CACHE_MISSES_KEY)
            pipeline.delete(CACHE_ERRORS_KEY)
            await pipeline.execute()
            return True
    except RedisError as e:
        logger.error(
            "Failed to reset cache stats",
            error=str(e),
            error_type=type(e).__name__
        )
        return False
