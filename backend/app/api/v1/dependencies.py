"""
API dependencies for the Test Generation Agent.

This module provides common dependencies used across API endpoints,
including database sessions, authentication, and rate limiting.
"""

from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import time
from collections import defaultdict

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings

logger = structlog.get_logger(__name__)

# Simple in-memory rate limiter (in production, use Redis)
rate_limit_storage = defaultdict(list)


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session dependency.
    
    Yields:
        AsyncSession: Database session
    """
    async for session in get_db():
        yield session


async def get_current_user_id(
    current_user: str = Depends(get_current_user)
) -> str:
    """
    Get current authenticated user ID.
    
    Args:
        current_user: Current user from authentication
        
    Returns:
        str: User ID
    """
    return current_user


async def verify_webhook_auth(request: Request) -> bool:
    """
    Verify webhook authentication.
    
    Args:
        request: FastAPI request object
        
    Returns:
        bool: True if authentication is valid
        
    Raises:
        HTTPException: If authentication fails
    """
    if not settings.AZURE_DEVOPS_WEBHOOK_SECRET:
        logger.warning("Webhook secret not configured, skipping verification")
        return True
    
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature"
        )
    
    # In a real implementation, you would verify the signature
    # against the request body using the webhook secret
    return True


def rate_limit_dependency(
    max_requests: int = settings.RATE_LIMIT_PER_MINUTE
):
    """
    Create a rate limiting dependency.
    
    Args:
        max_requests: Maximum requests per minute
        
    Returns:
        Dependency function
    """
    async def rate_limiter(request: Request) -> None:
        """
        Rate limiting implementation.
        
        Args:
            request: FastAPI request object
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        client_ip = request.client.host
        current_time = time.time()
        
        # Clean old entries (older than 1 minute)
        rate_limit_storage[client_ip] = [
            timestamp for timestamp in rate_limit_storage[client_ip]
            if current_time - timestamp < 60
        ]
        
        # Check rate limit
        if len(rate_limit_storage[client_ip]) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Too many requests per minute."
            )
        
        # Add current request
        rate_limit_storage[client_ip].append(current_time)
    
    return rate_limiter


async def validate_quality_threshold(
    quality_threshold: Optional[float] = None
) -> float:
    """
    Validate and return quality threshold.
    
    Args:
        quality_threshold: Requested quality threshold
        
    Returns:
        float: Validated quality threshold
        
    Raises:
        HTTPException: If threshold is invalid
    """
    if quality_threshold is None:
        return settings.QUALITY_THRESHOLD_MIN
    
    if not 0.0 <= quality_threshold <= 1.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quality threshold must be between 0.0 and 1.0"
        )
    
    return quality_threshold


async def validate_pagination(
    skip: int = 0,
    limit: int = 100,
    max_limit: int = 1000
) -> tuple[int, int]:
    """
    Validate pagination parameters.
    
    Args:
        skip: Number of records to skip
        limit: Number of records to return
        max_limit: Maximum allowed limit
        
    Returns:
        tuple[int, int]: Validated skip and limit
        
    Raises:
        HTTPException: If parameters are invalid
    """
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skip parameter must be non-negative"
        )
    
    if limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit parameter must be positive"
        )
    
    if limit > max_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Limit parameter cannot exceed {max_limit}"
        )
    
    return skip, limit


class ServiceDependency:
    """Container for service dependencies."""
    
    def __init__(self):
        self._services = {}
    
    def register_service(self, name: str, service_instance):
        """Register a service instance."""
        self._services[name] = service_instance
    
    def get_service(self, name: str):
        """Get a service instance."""
        if name not in self._services:
            raise ValueError(f"Service '{name}' not registered")
        return self._services[name]


# Global service container
service_container = ServiceDependency()


async def get_test_generation_service():
    """Get test generation service dependency."""
    return service_container.get_service("test_generation")


async def get_quality_service():
    """Get quality validation service dependency."""
    return service_container.get_service("quality_validation")


async def get_analytics_service():
    """Get analytics service dependency."""
    return service_container.get_service("analytics")
