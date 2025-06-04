"""
Redis-based session storage for the Test Generation Agent.

This module provides utilities for managing user sessions in Redis,
including session creation, validation, and cleanup.
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime, timedelta
from redis.exceptions import RedisError
import structlog

from app.core.config import settings
from app.core.redis import get_redis_client
from app.utils.correlation import get_correlation_logger

# Set up logger with correlation tracking
logger = get_correlation_logger(__name__)

# Redis key prefix for sessions
SESSION_KEY_PREFIX = "testgen:session:"
SESSION_INDEX_KEY = "testgen:sessions:index"


class Session:
    """Redis-based session class for managing user sessions."""
    
    def __init__(self, session_id: Optional[str] = None, ttl: Optional[int] = None):
        """
        Initialize a session.
        
        Args:
            session_id: Optional session ID (generated if not provided)
            ttl: Session time-to-live in seconds (None for default)
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.ttl = ttl or 86400  # Default 24 hours
        self.key = f"{SESSION_KEY_PREFIX}{self.session_id}"
    
    async def load(self) -> Dict[str, Any]:
        """
        Load session data from Redis.
        
        Returns:
            Session data as a dict
        """
        try:
            async with (await get_redis_client()) as client:
                data = await client.get(self.key)
                if data:
                    # Extend TTL on access
                    await client.expire(self.key, self.ttl)
                    return json.loads(data)
                return {}
        except RedisError as e:
            logger.error(
                "Failed to load session",
                session_id=self.session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return {}
    
    async def save(self, data: Dict[str, Any]) -> bool:
        """
        Save session data to Redis.
        
        Args:
            data: Session data to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with (await get_redis_client()) as client:
                pipeline = client.pipeline()
                pipeline.set(self.key, json.dumps(data), ex=self.ttl)
                pipeline.sadd(SESSION_INDEX_KEY, self.session_id)
                await pipeline.execute()
                return True
        except RedisError as e:
            logger.error(
                "Failed to save session",
                session_id=self.session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    async def update(self, updates: Dict[str, Any]) -> bool:
        """
        Update specific session data fields.
        
        Args:
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            current_data = await self.load()
            current_data.update(updates)
            return await self.save(current_data)
        except Exception as e:
            logger.error(
                "Failed to update session",
                session_id=self.session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    async def delete(self) -> bool:
        """
        Delete the session.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            async with (await get_redis_client()) as client:
                pipeline = client.pipeline()
                pipeline.delete(self.key)
                pipeline.srem(SESSION_INDEX_KEY, self.session_id)
                await pipeline.execute()
                return True
        except RedisError as e:
            logger.error(
                "Failed to delete session",
                session_id=self.session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    async def exists(self) -> bool:
        """
        Check if session exists.
        
        Returns:
            True if session exists, False otherwise
        """
        try:
            async with (await get_redis_client()) as client:
                return await client.exists(self.key) > 0
        except RedisError as e:
            logger.error(
                "Failed to check session existence",
                session_id=self.session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    async def touch(self) -> bool:
        """
        Extend session TTL without modifying data.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            async with (await get_redis_client()) as client:
                return await client.expire(self.key, self.ttl)
        except RedisError as e:
            logger.error(
                "Failed to touch session",
                session_id=self.session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return False


async def get_active_sessions() -> List[str]:
    """
    Get list of all active session IDs.
    
    Returns:
        List of active session IDs
    """
    try:
        async with (await get_redis_client()) as client:
            sessions = await client.smembers(SESSION_INDEX_KEY)
            return list(sessions)
    except RedisError as e:
        logger.error(
            "Failed to get active sessions",
            error=str(e),
            error_type=type(e).__name__
        )
        return []


async def clear_expired_sessions() -> int:
    """
    Clear expired sessions from the index.
    
    Returns:
        Number of expired sessions cleared
    """
    try:
        async with (await get_redis_client()) as client:
            # Get all session IDs
            session_ids = await client.smembers(SESSION_INDEX_KEY)
            pipeline = client.pipeline()
            
            # Check each session
            for sid in session_ids:
                key = f"{SESSION_KEY_PREFIX}{sid}"
                pipeline.exists(key)
            
            # Execute pipeline to check all sessions
            exist_results = await pipeline.execute()
            
            # Find expired sessions
            expired_ids = [
                sid for sid, exists in zip(session_ids, exist_results) 
                if not exists
            ]
            
            # Remove expired sessions from index
            if expired_ids:
                await client.srem(SESSION_INDEX_KEY, *expired_ids)
                logger.info(
                    "Cleared expired sessions",
                    count=len(expired_ids)
                )
            
            return len(expired_ids)
    except RedisError as e:
        logger.error(
            "Failed to clear expired sessions",
            error=str(e),
            error_type=type(e).__name__
        )
        return 0


async def get_session_count() -> int:
    """
    Get count of active sessions.
    
    Returns:
        Number of active sessions
    """
    try:
        async with (await get_redis_client()) as client:
            return await client.scard(SESSION_INDEX_KEY)
    except RedisError as e:
        logger.error(
            "Failed to get session count",
            error=str(e),
            error_type=type(e).__name__
        )
        return 0


async def delete_all_sessions() -> int:
    """
    Delete all sessions (use with caution).
    
    Returns:
        Number of sessions deleted
    """
    try:
        async with (await get_redis_client()) as client:
            # Get all session IDs
            session_ids = await client.smembers(SESSION_INDEX_KEY)
            count = len(session_ids)
            
            if count > 0:
                pipeline = client.pipeline()
                
                # Delete all session keys
                for sid in session_ids:
                    key = f"{SESSION_KEY_PREFIX}{sid}"
                    pipeline.delete(key)
                
                # Delete the index
                pipeline.delete(SESSION_INDEX_KEY)
                
                await pipeline.execute()
                
                logger.warning(
                    "All sessions deleted",
                    count=count
                )
            
            return count
    except RedisError as e:
        logger.error(
            "Failed to delete all sessions",
            error=str(e),
            error_type=type(e).__name__
        )
        return 0
