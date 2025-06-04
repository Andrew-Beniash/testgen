"""
Enhanced logging configuration for the Test Generation Agent.

This module sets up comprehensive structured logging with proper formatting,
context binding, correlation tracking, and output configuration.
"""

import sys
import os
import structlog
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger
import logging
import logging.handlers
from datetime import datetime

from app.core.config import settings


def setup_logging() -> None:
    """
    Configure comprehensive structured logging for the application.
    
    Sets up structlog with appropriate processors and formatters
    based on the configured log format and level, with correlation
    tracking and enhanced context management.
    """
    
    # Set log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper())
    
    # Configure processors based on format
    if settings.LOG_FORMAT.lower() == "json":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_app_context,  # Custom processor for app context
            structlog.processors.JSONRenderer()
        ]
        
        # Configure JSON formatter for standard library logging
        formatter = EnhancedJSONFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S"
        )
    else:
        # Human-readable format for development
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_app_context,  # Custom processor for app context
            structlog.dev.ConsoleRenderer(colors=True)
        ]
        
        formatter = EnhancedFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if settings.LOG_FILE:
        # Ensure log directory exists
        log_dir = os.path.dirname(settings.LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Use rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            filename=settings.LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    configure_third_party_loggers(log_level)
    
    # Log successful logging setup
    logger = structlog.get_logger(__name__)
    logger.info(
        "Logging system initialized",
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
        log_file=settings.LOG_FILE,
        environment=settings.ENVIRONMENT
    )


def configure_third_party_loggers(log_level: int) -> None:
    """
    Configure third-party library loggers.
    
    Args:
        log_level: The log level to set
    """
    
    # Reduce noise from third-party libraries
    noisy_loggers = [
        "uvicorn.access",
        "uvicorn.error",
        "httpx",
        "httpcore",
        "openai",
        "asyncio",
        "urllib3",
        "requests",
        "aiohttp",
        "multipart",
    ]
    
    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        # Set to WARNING unless we're in DEBUG mode
        if log_level == logging.DEBUG:
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.WARNING)
    
    # Configure database logging
    if settings.DATABASE_ECHO:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    
    # Configure special application loggers
    logging.getLogger("app.security").setLevel(log_level)
    logging.getLogger("app.performance").setLevel(logging.INFO)


def add_app_context(logger, name, event_dict):
    """
    Custom processor to add application context to log entries.
    
    Args:
        logger: Logger instance
        name: Logger name
        event_dict: Event dictionary to modify
        
    Returns:
        dict: Modified event dictionary with app context
    """
    # Add application metadata
    event_dict["app_name"] = settings.APP_NAME
    event_dict["app_version"] = settings.APP_VERSION
    event_dict["environment"] = settings.ENVIRONMENT
    
    # Add timestamp if not present
    if "timestamp" not in event_dict:
        event_dict["timestamp"] = datetime.utcnow().isoformat()
    
    return event_dict


class EnhancedJSONFormatter(jsonlogger.JsonFormatter):
    """Enhanced JSON formatter with additional context and correlation tracking."""
    
    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add correlation ID if available
        correlation_id = getattr(record, 'correlation_id', None)
        if correlation_id:
            log_record['correlation_id'] = correlation_id
        
        # Add thread/process info for debugging
        log_record['thread_id'] = record.thread
        log_record['process_id'] = record.process
        
        # Add hostname for distributed deployments
        log_record['hostname'] = os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        
        # Ensure timestamp is properly formatted
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().isoformat()


class EnhancedFormatter(logging.Formatter):
    """Enhanced formatter with correlation ID and additional context."""
    
    def format(self, record):
        """Format log record with enhanced context."""
        # Add correlation ID if not present
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = getattr(record, 'correlation_id', 'no-correlation')
        
        # Add hostname for distributed deployments
        if not hasattr(record, 'hostname'):
            record.hostname = os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        
        return super().format(record)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger for a module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        structlog.BoundLogger: Configured logger
    """
    return structlog.get_logger(name)


def bind_context(**kwargs) -> None:
    """
    Bind additional context to the current logging context.
    
    Args:
        **kwargs: Key-value pairs to bind to logging context
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear the current logging context."""
    structlog.contextvars.clear_contextvars()


def with_context(**context):
    """
    Decorator to add context to all log messages within a function.
    
    Args:
        **context: Context to add to log messages
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Save current context
            token = structlog.contextvars.bind_contextvars(**context)
            try:
                return func(*args, **kwargs)
            finally:
                # Clear the bound context
                structlog.contextvars.clear_contextvars()
        return wrapper
    return decorator


class StructuredLogger:
    """
    Enhanced structured logger with built-in context management and 
    correlation tracking for comprehensive application logging.
    """
    
    def __init__(self, name: str, default_context: Optional[Dict[str, Any]] = None):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
            default_context: Default context to include in all log messages
        """
        self.logger = structlog.get_logger(name)
        self.default_context = default_context or {}
        self.name = name
    
    def _merge_context(self, **kwargs) -> Dict[str, Any]:
        """Merge default context with provided context."""
        context = self.default_context.copy()
        context.update(kwargs)
        return context
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with context."""
        self.logger.debug(message, **self._merge_context(**kwargs))
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with context."""
        self.logger.info(message, **self._merge_context(**kwargs))
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with context."""
        self.logger.warning(message, **self._merge_context(**kwargs))
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with context."""
        self.logger.error(message, **self._merge_context(**kwargs))
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message with context."""
        self.logger.critical(message, **self._merge_context(**kwargs))
    
    def exception(self, message: str, exc_info: bool = True, **kwargs) -> None:
        """Log exception with context."""
        self.logger.error(message, exc_info=exc_info, **self._merge_context(**kwargs))
    
    def bind(self, **kwargs) -> 'StructuredLogger':
        """
        Create a new logger instance with additional bound context.
        
        Args:
            **kwargs: Additional context to bind
            
        Returns:
            StructuredLogger: New logger instance with bound context
        """
        new_context = self.default_context.copy()
        new_context.update(kwargs)
        return StructuredLogger(self.name, new_context)


# Global logging instances for common use cases
application_logger = StructuredLogger("app", {"component": "application"})
security_logger = StructuredLogger("app.security", {"component": "security"})
performance_logger = StructuredLogger("app.performance", {"component": "performance"})
audit_logger = StructuredLogger("app.audit", {"component": "audit"})


class LoggingMiddleware:
    """Enhanced middleware for request/response logging with correlation tracking."""
    
    def __init__(self, logger_name: str = "api"):
        self.logger = StructuredLogger(logger_name, {"component": "api"})
    
    async def log_request(self, request: Any, **kwargs) -> None:
        """Log incoming request with enhanced context."""
        self.logger.info(
            "Request received",
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            query_params=dict(request.query_params),
            user_agent=request.headers.get("user-agent", ""),
            content_type=request.headers.get("content-type", ""),
            event_type="http_request",
            **kwargs
        )
    
    async def log_response(self, response: Any, processing_time: float = None, **kwargs) -> None:
        """Log outgoing response with enhanced context."""
        log_data = {
            "status_code": response.status_code,
            "event_type": "http_response"
        }
        
        if processing_time is not None:
            log_data["processing_time_ms"] = round(processing_time * 1000, 2)
        
        log_data.update(kwargs)
        
        # Choose log level based on status code
        if response.status_code >= 500:
            self.logger.error("Response sent", **log_data)
        elif response.status_code >= 400:
            self.logger.warning("Response sent", **log_data)
        else:
            self.logger.info("Response sent", **log_data)
    
    async def log_error(self, error: Exception, processing_time: float = None, **kwargs) -> None:
        """Log error with enhanced context."""
        log_data = {
            "error": str(error),
            "error_type": type(error).__name__,
            "event_type": "http_error"
        }
        
        if processing_time is not None:
            log_data["processing_time_ms"] = round(processing_time * 1000, 2)
        
        log_data.update(kwargs)
        
        self.logger.error("Error occurred", **log_data)


# Global logging middleware instance
logging_middleware = LoggingMiddleware()
