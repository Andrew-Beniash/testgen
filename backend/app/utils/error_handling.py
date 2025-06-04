"""
Error handling utilities for common error scenarios in the Test Generation Agent.

This module provides utility functions and decorators for handling common
error patterns, retries, timeouts, and error conversion across the application.
"""

import asyncio
import functools
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union, TypeVar, Awaitable
from contextlib import asynccontextmanager
import structlog

from app.core.exceptions import (
    BaseTestGenException,
    TimeoutException,
    ExternalServiceException,
    DatabaseException,
    ConfigurationException,
    ErrorCode,
    ErrorCategory
)
from app.utils.correlation import get_correlation_logger

T = TypeVar('T')
logger = get_correlation_logger(__name__)


def handle_errors(
    *,
    exceptions: Union[Type[Exception], tuple] = Exception,
    default_value: Any = None,
    log_errors: bool = True,
    reraise_as: Optional[Type[BaseTestGenException]] = None,
    error_message: Optional[str] = None
):
    """
    Decorator to handle exceptions with optional error conversion and logging.
    
    Args:
        exceptions: Exception types to catch
        default_value: Value to return if exception occurs
        log_errors: Whether to log caught exceptions
        reraise_as: Exception type to convert caught exceptions to
        error_message: Custom error message for converted exceptions
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_errors:
                    logger.error(
                        f"Error in {func.__name__}",
                        function=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                        args=str(args)[:200],
                        kwargs=str(kwargs)[:200]
                    )
                
                if reraise_as:
                    message = error_message or f"Error in {func.__name__}: {str(e)}"
                    raise reraise_as(message, cause=e)
                
                if default_value is not None:
                    return default_value
                
                raise
        
        return wrapper
    return decorator


def handle_async_errors(
    *,
    exceptions: Union[Type[Exception], tuple] = Exception,
    default_value: Any = None,
    log_errors: bool = True,
    reraise_as: Optional[Type[BaseTestGenException]] = None,
    error_message: Optional[str] = None
):
    """
    Async version of handle_errors decorator.
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                if log_errors:
                    logger.error(
                        f"Error in {func.__name__}",
                        function=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                        args=str(args)[:200],
                        kwargs=str(kwargs)[:200]
                    )
                
                if reraise_as:
                    message = error_message or f"Error in {func.__name__}: {str(e)}"
                    raise reraise_as(message, cause=e)
                
                if default_value is not None:
                    return default_value
                
                raise
        
        return wrapper
    return decorator


def with_timeout(
    timeout_seconds: float,
    error_message: Optional[str] = None
):
    """
    Decorator to add timeout functionality to async functions.
    
    Args:
        timeout_seconds: Timeout in seconds
        error_message: Custom error message for timeout
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                message = error_message or f"Function {func.__name__} timed out after {timeout_seconds} seconds"
                logger.warning(
                    "Function timeout",
                    function=func.__name__,
                    timeout_seconds=timeout_seconds,
                    args=str(args)[:200],
                    kwargs=str(kwargs)[:200]
                )
                raise TimeoutException(
                    operation=func.__name__,
                    timeout_seconds=int(timeout_seconds)
                )
        
        return wrapper
    return decorator


def with_retry(
    *,
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
    on_retry: Optional[Callable[[int, Exception], None]] = None
):
    """
    Decorator to add retry functionality to functions.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        backoff_factor: Factor to multiply delay by after each retry
        exceptions: Exception types to retry on
        on_retry: Callback function called on each retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = delay_seconds
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            function=func.__name__,
                            max_attempts=max_attempts,
                            final_error=str(e),
                            error_type=type(e).__name__
                        )
                        raise
                    
                    # Log retry attempt
                    logger.warning(
                        f"Function {func.__name__} failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        error=str(e),
                        error_type=type(e).__name__,
                        retry_delay=delay
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt + 1, e)
                    
                    # Wait before retry
                    time.sleep(delay)
                    delay *= backoff_factor
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def with_async_retry(
    *,
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
    on_retry: Optional[Callable[[int, Exception], Awaitable[None]]] = None
):
    """
    Async version of with_retry decorator.
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = delay_seconds
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            function=func.__name__,
                            max_attempts=max_attempts,
                            final_error=str(e),
                            error_type=type(e).__name__
                        )
                        raise
                    
                    # Log retry attempt
                    logger.warning(
                        f"Function {func.__name__} failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        error=str(e),
                        error_type=type(e).__name__,
                        retry_delay=delay
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        await on_retry(attempt + 1, e)
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


@asynccontextmanager
async def error_context(
    operation_name: str,
    *,
    log_success: bool = True,
    log_errors: bool = True,
    reraise_as: Optional[Type[BaseTestGenException]] = None
):
    """
    Async context manager for comprehensive error handling and logging.
    
    Args:
        operation_name: Name of the operation being performed
        log_success: Whether to log successful completion
        log_errors: Whether to log errors
        reraise_as: Exception type to convert errors to
    """
    start_time = time.time()
    
    logger.debug(f"Starting operation: {operation_name}")
    
    try:
        yield
        
        duration = time.time() - start_time
        
        if log_success:
            logger.info(
                f"Operation completed successfully: {operation_name}",
                operation=operation_name,
                duration_seconds=round(duration, 3),
                event_type="operation_success"
            )
    
    except Exception as e:
        duration = time.time() - start_time
        
        if log_errors:
            logger.error(
                f"Operation failed: {operation_name}",
                operation=operation_name,
                duration_seconds=round(duration, 3),
                error=str(e),
                error_type=type(e).__name__,
                event_type="operation_failure"
            )
        
        if reraise_as:
            raise reraise_as(
                f"Operation '{operation_name}' failed: {str(e)}",
                cause=e
            )
        
        raise


class ErrorAggregator:
    """
    Utility class to collect and aggregate multiple errors for batch operations.
    """
    
    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
        self.operation_count = 0
        self.success_count = 0
    
    def add_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        item_id: Optional[str] = None
    ) -> None:
        """Add an error to the aggregator."""
        error_info = {
            "error": str(error),
            "error_type": type(error).__name__,
            "context": context or {},
            "item_id": item_id,
            "timestamp": time.time()
        }
        
        if isinstance(error, BaseTestGenException):
            error_info.update({
                "error_code": error.error_code.value,
                "category": error.category.value,
                "details": error.details
            })
        
        self.errors.append(error_info)
    
    def add_success(self, item_id: Optional[str] = None) -> None:
        """Record a successful operation."""
        self.success_count += 1
        self.operation_count += 1
    
    def add_operation(self) -> None:
        """Record an operation attempt."""
        self.operation_count += 1
    
    @property
    def has_errors(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0
    
    @property
    def error_count(self) -> int:
        """Get the number of errors."""
        return len(self.errors)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.operation_count == 0:
            return 0.0
        return self.success_count / self.operation_count
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all operations and errors."""
        return {
            "total_operations": self.operation_count,
            "successful_operations": self.success_count,
            "failed_operations": self.error_count,
            "success_rate": round(self.success_rate, 3),
            "errors": self.errors
        }
    
    def log_summary(self, operation_name: str = "batch_operation") -> None:
        """Log a summary of the aggregated errors."""
        summary = self.get_summary()
        
        if self.has_errors:
            logger.warning(
                f"Batch operation completed with errors: {operation_name}",
                operation=operation_name,
                summary=summary,
                event_type="batch_operation_partial_failure"
            )
        else:
            logger.info(
                f"Batch operation completed successfully: {operation_name}",
                operation=operation_name,
                summary=summary,
                event_type="batch_operation_success"
            )


def convert_external_exception(
    exception: Exception,
    service_name: str,
    operation: str
) -> BaseTestGenException:
    """
    Convert external service exceptions to internal exceptions.
    
    Args:
        exception: The original exception
        service_name: Name of the external service
        operation: Operation that was being performed
        
    Returns:
        BaseTestGenException: Converted exception
    """
    # Map common exception types
    if "timeout" in str(exception).lower():
        return TimeoutException(
            operation=f"{service_name}:{operation}",
            timeout_seconds=30,  # Default timeout
            cause=exception
        )
    
    if "connection" in str(exception).lower():
        return ExternalServiceException(
            service_name=service_name,
            message=f"Connection error during {operation}: {str(exception)}",
            cause=exception
        )
    
    if "auth" in str(exception).lower() or "unauthorized" in str(exception).lower():
        return ExternalServiceException(
            service_name=service_name,
            message=f"Authentication error during {operation}: {str(exception)}",
            error_code=ErrorCode.AUTHENTICATION_FAILED,
            cause=exception
        )
    
    # Default conversion
    return ExternalServiceException(
        service_name=service_name,
        message=f"Error during {operation}: {str(exception)}",
        cause=exception
    )


def create_validation_error_details(validation_errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create structured error details from validation errors.
    
    Args:
        validation_errors: List of validation error dictionaries
        
    Returns:
        Dict: Structured error details
    """
    field_errors = []
    
    for error in validation_errors:
        field_errors.append({
            "field": error.get("field", "unknown"),
            "message": error.get("message", "Validation failed"),
            "code": error.get("code", "VALIDATION_ERROR"),
            "value": error.get("value")
        })
    
    return {
        "field_errors": field_errors,
        "validation_errors": [err["message"] for err in field_errors]
    }


# Utility functions for common error scenarios
async def safe_external_call(
    func: Callable[..., Awaitable[T]],
    service_name: str,
    operation: str,
    *args,
    **kwargs
) -> T:
    """
    Safely call an external service with proper error handling and conversion.
    
    Args:
        func: The async function to call
        service_name: Name of the external service
        operation: Operation being performed
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the function call
        
    Raises:
        BaseTestGenException: Converted exception on failure
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        # Convert to internal exception
        converted_exception = convert_external_exception(e, service_name, operation)
        
        # Log the conversion
        logger.warning(
            "External service call failed, converted exception",
            service_name=service_name,
            operation=operation,
            original_error=str(e),
            original_error_type=type(e).__name__,
            converted_error_code=converted_exception.error_code.value,
            converted_error_category=converted_exception.category.value
        )
        
        raise converted_exception


def ensure_error_logged(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: str = "error"
) -> None:
    """
    Ensure an error is properly logged with context.
    
    Args:
        error: The exception to log
        context: Additional context to include
        level: Log level to use
    """
    log_method = getattr(logger, level, logger.error)
    
    log_data = {
        "error": str(error),
        "error_type": type(error).__name__,
        "event_type": "error_logged"
    }
    
    if context:
        log_data.update(context)
    
    if isinstance(error, BaseTestGenException):
        log_data.update({
            "error_code": error.error_code.value,
            "category": error.category.value,
            "status_code": error.status_code,
            "details": error.details
        })
    
    log_method("Error logged", **log_data)
