"""
Cache invalidation strategies for the Test Generation Agent.

This module provides advanced cache invalidation strategies including:
- Tag-based invalidation
- Entity-based invalidation
- Time-based invalidation
- Batch invalidation
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Set, Union
from redis.exceptions import RedisError
import structlog

from app.core.config import settings
from app.core.redis import get_redis_client
from app.utils.correlation import get_correlation_logger
from app.utils.cache import cache_delete, cache_delete_pattern

# Set up logger with correlation tracking
logger = get_correlation_logger(__name__)

# Redis key prefixes for cache invalidation
TAG_KEY_PREFIX = "testgen:tags:"
ENTITY_KEY_PREFIX = "testgen:entities:"
INVALIDATION_LOCKS_PREFIX = "testgen:invalidation:locks:"


async def tag_keys(tag: str, key: str) -> bool:
    """
    Tag a cache key for group invalidation.
    
    Args:
        tag: The tag name
        key: The cache key to tag
        
    Returns:
        True if successful, False otherwise
    """
    tag_set_key = f"{TAG_KEY_PREFIX}{tag}"
    try:
        async with (await get_redis_client()) as client:
            await client.sadd(tag_set_key, key)
            return True
    except RedisError as e:
        logger.error(
            "Failed to tag cache key",
            tag=tag,
            key=key,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def invalidate_tag(tag: str) -> int:
    """
    Invalidate all cache keys with a specific tag.
    
    Args:
        tag: The tag name
        
    Returns:
        Number of keys invalidated
    """
    tag_set_key = f"{TAG_KEY_PREFIX}{tag}"
    try:
        async with (await get_redis_client()) as client:
            # Get all keys with this tag
            keys = await client.smembers(tag_set_key)
            
            if not keys:
                return 0
            
            # Delete all keys
            pipeline = client.pipeline()
            for key in keys:
                pipeline.delete(key)
            
            # Delete the tag set itself
            pipeline.delete(tag_set_key)
            
            results = await pipeline.execute()
            
            # Count successful deletions (exclude the tag set deletion result)
            deleted_count = sum(1 for result in results[:-1] if result)
            
            logger.info(
                "Cache tag invalidated",
                tag=tag,
                keys_count=len(keys),
                deleted_count=deleted_count
            )
            
            return deleted_count
    except RedisError as e:
        logger.error(
            "Failed to invalidate tag",
            tag=tag,
            error=str(e),
            error_type=type(e).__name__
        )
        return 0


async def register_entity_key(entity_type: str, entity_id: str, key: str) -> bool:
    """
    Register a cache key as associated with an entity.
    
    Args:
        entity_type: The entity type (e.g., 'user', 'test_case')
        entity_id: The entity ID
        key: The cache key to register
        
    Returns:
        True if successful, False otherwise
    """
    entity_set_key = f"{ENTITY_KEY_PREFIX}{entity_type}:{entity_id}"
    try:
        async with (await get_redis_client()) as client:
            await client.sadd(entity_set_key, key)
            return True
    except RedisError as e:
        logger.error(
            "Failed to register entity key",
            entity_type=entity_type,
            entity_id=entity_id,
            key=key,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def invalidate_entity(entity_type: str, entity_id: str) -> int:
    """
    Invalidate all cache keys associated with an entity.
    
    Args:
        entity_type: The entity type
        entity_id: The entity ID
        
    Returns:
        Number of keys invalidated
    """
    entity_set_key = f"{ENTITY_KEY_PREFIX}{entity_type}:{entity_id}"
    try:
        async with (await get_redis_client()) as client:
            # Get all keys for this entity
            keys = await client.smembers(entity_set_key)
            
            if not keys:
                return 0
            
            # Delete all keys
            pipeline = client.pipeline()
            for key in keys:
                pipeline.delete(key)
            
            # Delete the entity set itself
            pipeline.delete(entity_set_key)
            
            results = await pipeline.execute()
            
            # Count successful deletions (exclude the entity set deletion result)
            deleted_count = sum(1 for result in results[:-1] if result)
            
            logger.info(
                "Cache entity invalidated",
                entity_type=entity_type,
                entity_id=entity_id,
                keys_count=len(keys),
                deleted_count=deleted_count
            )
            
            return deleted_count
    except RedisError as e:
        logger.error(
            "Failed to invalidate entity",
            entity_type=entity_type,
            entity_id=entity_id,
            error=str(e),
            error_type=type(e).__name__
        )
        return 0


async def invalidate_all_entity_type(entity_type: str) -> int:
    """
    Invalidate all cache keys for a specific entity type.
    
    Args:
        entity_type: The entity type
        
    Returns:
        Number of keys invalidated
    """
    pattern = f"{ENTITY_KEY_PREFIX}{entity_type}:*"
    try:
        async with (await get_redis_client()) as client:
            # Find all entity sets for this type
            entity_sets = []
            async for key in client.scan_iter(match=pattern):
                entity_sets.append(key)
            
            if not entity_sets:
                return 0
            
            total_deleted = 0
            
            # For each entity set, get and delete its keys
            for entity_set in entity_sets:
                # Get all keys in this entity set
                keys = await client.smembers(entity_set)
                
                if keys:
                    # Delete all keys
                    pipeline = client.pipeline()
                    for key in keys:
                        pipeline.delete(key)
                    
                    results = await pipeline.execute()
                    deleted_count = sum(1 for result in results if result)
                    total_deleted += deleted_count
            
            # Delete all entity sets
            if entity_sets:
                await client.delete(*entity_sets)
            
            logger.info(
                "Cache entity type invalidated",
                entity_type=entity_type,
                entity_sets_count=len(entity_sets),
                deleted_count=total_deleted
            )
            
            return total_deleted
    except RedisError as e:
        logger.error(
            "Failed to invalidate entity type",
            entity_type=entity_type,
            error=str(e),
            error_type=type(e).__name__
        )
        return 0


async def acquire_invalidation_lock(lock_name: str, ttl: int = 30) -> bool:
    """
    Acquire a distributed lock for safe cache invalidation.
    
    Args:
        lock_name: Name of the lock
        ttl: Time-to-live in seconds
        
    Returns:
        True if lock acquired, False otherwise
    """
    lock_key = f"{INVALIDATION_LOCKS_PREFIX}{lock_name}"
    try:
        async with (await get_redis_client()) as client:
            # Try to set the lock key with NX (only if it doesn't exist)
            return await client.set(lock_key, "1", ex=ttl, nx=True)
    except RedisError as e:
        logger.error(
            "Failed to acquire invalidation lock",
            lock_name=lock_name,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def release_invalidation_lock(lock_name: str) -> bool:
    """
    Release a distributed lock.
    
    Args:
        lock_name: Name of the lock
        
    Returns:
        True if lock released, False otherwise
    """
    lock_key = f"{INVALIDATION_LOCKS_PREFIX}{lock_name}"
    try:
        async with (await get_redis_client()) as client:
            return await client.delete(lock_key) > 0
    except RedisError as e:
        logger.error(
            "Failed to release invalidation lock",
            lock_name=lock_name,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def scheduled_invalidation(pattern: str, ttl: int = 3600) -> bool:
    """
    Schedule pattern-based cache invalidation.
    
    This creates a record of when to invalidate a pattern,
    which can be executed by a background task.
    
    Args:
        pattern: The key pattern to invalidate
        ttl: Time in seconds until invalidation
        
    Returns:
        True if scheduled, False otherwise
    """
    schedule_key = f"testgen:scheduled_invalidations"
    invalidation_time = int(time.time()) + ttl
    try:
        async with (await get_redis_client()) as client:
            # Add to sorted set with score as invalidation time
            await client.zadd(schedule_key, {pattern: invalidation_time})
            return True
    except RedisError as e:
        logger.error(
            "Failed to schedule invalidation",
            pattern=pattern,
            ttl=ttl,
            error=str(e),
            error_type=type(e).__name__
        )
        return False


async def process_scheduled_invalidations() -> int:
    """
    Process all scheduled invalidations that are due.
    
    This should be called by a background task periodically.
    
    Returns:
        Number of patterns invalidated
    """
    schedule_key = f"testgen:scheduled_invalidations"
    now = int(time.time())
    try:
        async with (await get_redis_client()) as client:
            # Get all patterns due for invalidation
            due_patterns = await client.zrangebyscore(
                schedule_key, 0, now
            )
            
            if not due_patterns:
                return 0
            
            invalidated_count = 0
            
            # Process each pattern
            for pattern in due_patterns:
                # Invalidate the pattern
                deleted = await cache_delete_pattern(pattern)
                invalidated_count += 1
                
                logger.info(
                    "Processed scheduled invalidation",
                    pattern=pattern,
                    keys_deleted=deleted
                )
            
            # Remove processed patterns from the set
            await client.zremrangebyscore(schedule_key, 0, now)
            
            return invalidated_count
    except RedisError as e:
        logger.error(
            "Failed to process scheduled invalidations",
            error=str(e),
            error_type=type(e).__name__
        )
        return 0


async def get_scheduled_invalidations() -> List[Dict[str, Any]]:
    """
    Get list of all scheduled invalidations.
    
    Returns:
        List of dicts with pattern and invalidation time
    """
    schedule_key = f"testgen:scheduled_invalidations"
    try:
        async with (await get_redis_client()) as client:
            # Get all patterns with their scores
            results = await client.zrange(
                schedule_key, 0, -1, withscores=True
            )
            
            return [
                {
                    "pattern": pattern,
                    "invalidation_time": int(score),
                    "invalidation_time_str": time.strftime(
                        '%Y-%m-%d %H:%M:%S', 
                        time.localtime(score)
                    ),
                    "seconds_remaining": int(score - time.time())
                }
                for pattern, score in results
            ]
    except RedisError as e:
        logger.error(
            "Failed to get scheduled invalidations",
            error=str(e),
            error_type=type(e).__name__
        )
        return []


async def invalidate_pattern_with_lock(pattern: str) -> int:
    """
    Safely invalidate a pattern with distributed locking.
    
    Args:
        pattern: The key pattern to invalidate
        
    Returns:
        Number of keys invalidated
    """
    lock_name = f"pattern:{pattern.replace('*', '_star_')}"
    
    # Try to acquire the lock
    if not await acquire_invalidation_lock(lock_name, ttl=30):
        logger.warning(
            "Failed to acquire lock for pattern invalidation",
            pattern=pattern
        )
        return 0
    
    try:
        # Perform the invalidation
        return await cache_delete_pattern(pattern)
    finally:
        # Always release the lock
        await release_invalidation_lock(lock_name)
