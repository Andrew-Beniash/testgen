"""
Logging configuration for the Test Generation Agent.

This module sets up structured logging with proper formatting,
context binding, and output configuration.
"""

import sys
import structlog
from typing import Any
from pythonjsonlogger import jsonlogger
import logging

from app.core.config import settings


def setup_logging() -> None:
    """
    Configure structured logging for the application.
    
    Sets up structlog with appropriate processors and formatters
    based on the configured log format and level.
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
            structlog.processors.JSONRenderer()
        ]
        
        # Configure JSON formatter for standard library logging
        formatter = jsonlogger.JsonFormatter(
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
            structlog.dev.ConsoleRenderer(colors=True)
        ]
        
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
        file_handler = logging.FileHandler(settings.LOG_FILE)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    configure_third_party_loggers(log_level)


def configure_third_party_loggers(log_level: int) -> None:
    """
    Configure third-party library loggers.
    
    Args:
        log_level: The log level to set
    """
    
    # Reduce noise from third-party libraries
    noisy_loggers = [
        "uvicorn.access",
        "httpx",
        "httpcore",
        "openai",
        "asyncio",
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
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger for a module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        structlog.BoundLogger: Configured logger
    """
    return structlog.get_logger(name)


class LoggingMiddleware:
    """Middleware for request/response logging."""
    
    def __init__(self, logger_name: str = "api"):
        self.logger = get_logger(logger_name)
    
    async def log_request(self, request: Any, **kwargs) -> None:
        """Log incoming request."""
        self.logger.info(
            "Request received",
            method=request.method,
            url=str(request.url),
            **kwargs
        )
    
    async def log_response(self, response: Any, **kwargs) -> None:
        """Log outgoing response."""
        self.logger.info(
            "Response sent",
            status_code=response.status_code,
            **kwargs
        )
    
    async def log_error(self, error: Exception, **kwargs) -> None:
        """Log error."""
        self.logger.error(
            "Error occurred",
            error=str(error),
            error_type=type(error).__name__,
            **kwargs
        )


# Global logging middleware instance
logging_middleware = LoggingMiddleware()
