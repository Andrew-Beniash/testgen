"""
Correlation ID utilities for request tracking.

This module provides utilities for generating, managing, and tracking
correlation IDs across the entire request lifecycle.
"""

import uuid
import contextvars
from typing import Optional, Dict, Any
from fastapi import Request, Response
import structlog

# Context variable for storing correlation ID
correlation_id_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)


class CorrelationIdGenerator:
    """Generates unique correlation IDs for request tracking."""
    
    @staticmethod
    def generate() -> str:
        """Generate a new correlation ID."""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_short() -> str:
        """Generate a shorter correlation ID for display purposes."""
        return str(uuid.uuid4())[:8]


class CorrelationIdManager:
    """Manages correlation IDs throughout the request lifecycle."""
    
    HEADER_NAME = "X-Correlation-ID"
    REQUEST_ID_HEADER = "X-Request-ID"
    
    @classmethod
    def get_correlation_id(cls) -> Optional[str]:
        """Get the current correlation ID from context."""
        return correlation_id_context.get()
    
    @classmethod
    def set_correlation_id(cls, correlation_id: str) -> None:
        """Set the correlation ID in context."""
        correlation_id_context.set(correlation_id)
        
        # Also bind to structlog context
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    
    @classmethod
    def extract_from_request(cls, request: Request) -> str:
        """
        Extract correlation ID from request headers or generate a new one.
        
        Args:
            request: FastAPI request object
            
        Returns:
            str: Correlation ID
        """
        # Try to get from custom header first
        correlation_id = request.headers.get(cls.HEADER_NAME)
        
        # Fall back to request ID header
        if not correlation_id:
            correlation_id = request.headers.get(cls.REQUEST_ID_HEADER)
        
        # Generate new one if not found
        if not correlation_id:
            correlation_id = CorrelationIdGenerator.generate()
        
        return correlation_id
    
    @classmethod
    def add_to_response(cls, response: Response, correlation_id: str) -> None:
        """
        Add correlation ID to response headers.
        
        Args:
            response: FastAPI response object
            correlation_id: Correlation ID to add
        """
        response.headers[cls.HEADER_NAME] = correlation_id
        response.headers[cls.REQUEST_ID_HEADER] = correlation_id
    
    @classmethod
    def create_child_id(cls, parent_id: Optional[str] = None) -> str:
        """
        Create a child correlation ID for sub-operations.
        
        Args:
            parent_id: Parent correlation ID (uses current if not provided)
            
        Returns:
            str: Child correlation ID
        """
        parent = parent_id or cls.get_correlation_id()
        child_suffix = CorrelationIdGenerator.generate_short()
        
        if parent:
            return f"{parent}-{child_suffix}"
        else:
            return child_suffix


class CorrelationLogger:
    """Logger that automatically includes correlation ID in all log entries."""
    
    def __init__(self, logger_name: str):
        self.logger = structlog.get_logger(logger_name)
    
    def _get_context(self, **kwargs) -> Dict[str, Any]:
        """Get logging context with correlation ID."""
        context = kwargs.copy()
        
        correlation_id = CorrelationIdManager.get_correlation_id()
        if correlation_id:
            context["correlation_id"] = correlation_id
        
        return context
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with correlation ID."""
        self.logger.debug(message, **self._get_context(**kwargs))
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with correlation ID."""
        self.logger.info(message, **self._get_context(**kwargs))
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with correlation ID."""
        self.logger.warning(message, **self._get_context(**kwargs))
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with correlation ID."""
        self.logger.error(message, **self._get_context(**kwargs))
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message with correlation ID."""
        self.logger.critical(message, **self._get_context(**kwargs))
    
    def exception(self, message: str, exc_info: bool = True, **kwargs) -> None:
        """Log exception with correlation ID."""
        self.logger.error(message, exc_info=exc_info, **self._get_context(**kwargs))


def get_correlation_logger(name: str) -> CorrelationLogger:
    """
    Get a correlation-aware logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        CorrelationLogger: Logger instance that includes correlation ID
    """
    return CorrelationLogger(name)


# Decorator for functions that should create new correlation contexts
def with_correlation_id(correlation_id: Optional[str] = None):
    """
    Decorator to run a function with a specific correlation ID context.
    
    Args:
        correlation_id: Specific correlation ID to use (generates new if None)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Save current context
            current_id = CorrelationIdManager.get_correlation_id()
            
            # Set new correlation ID
            new_id = correlation_id or CorrelationIdGenerator.generate()
            CorrelationIdManager.set_correlation_id(new_id)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Restore previous context
                if current_id:
                    CorrelationIdManager.set_correlation_id(current_id)
                else:
                    correlation_id_context.set(None)
        
        return wrapper
    return decorator


async def with_correlation_id_async(correlation_id: Optional[str] = None):
    """
    Async context manager for correlation ID context.
    
    Args:
        correlation_id: Specific correlation ID to use (generates new if None)
    """
    class CorrelationContext:
        def __init__(self, corr_id: Optional[str]):
            self.correlation_id = corr_id or CorrelationIdGenerator.generate()
            self.previous_id = None
        
        async def __aenter__(self):
            self.previous_id = CorrelationIdManager.get_correlation_id()
            CorrelationIdManager.set_correlation_id(self.correlation_id)
            return self.correlation_id
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.previous_id:
                CorrelationIdManager.set_correlation_id(self.previous_id)
            else:
                correlation_id_context.set(None)
    
    return CorrelationContext(correlation_id)
