"""
Global exception handler for the Test Generation Agent.

This module provides comprehensive exception handling with proper error
categorization, logging, monitoring, and user-friendly responses.
"""

import traceback
from typing import Dict, Any, Optional, Union
from fastapi import Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import (
    SQLAlchemyError, 
    IntegrityError, 
    DataError, 
    OperationalError,
    NoResultFound
)
import structlog

from app.core.exceptions import (
    BaseTestGenException,
    ErrorCode,
    ErrorCategory,
    ValidationException,
    DatabaseException,
    RecordNotFoundException,
    DuplicateRecordException,
    ExternalServiceException,
    ConfigurationException,
    RateLimitExceededException,
    TimeoutException,
)
from app.schemas.error import (
    ErrorResponse,
    ValidationErrorResponse,
    ErrorDetails,
    FieldError,
    ErrorSeverity,
)
from app.utils.correlation import CorrelationIdManager, get_correlation_logger


class GlobalExceptionHandler:
    """
    Global exception handler that provides comprehensive error handling,
    logging, and monitoring for all application exceptions.
    """
    
    def __init__(self):
        self.logger = get_correlation_logger(__name__)
    
    async def handle_base_test_gen_exception(
        self, 
        request: Request, 
        exc: BaseTestGenException
    ) -> JSONResponse:
        """Handle custom application exceptions."""
        
        # Log the exception with appropriate level
        await self._log_exception(request, exc)
        
        # Create error response
        error_response = ErrorResponse(
            error_code=exc.error_code,
            category=exc.category,
            message=exc.user_message,
            details=self._create_error_details(exc),
            request_id=CorrelationIdManager.get_correlation_id(),
            severity=self._get_error_severity(exc)
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump()
        )
    
    async def handle_validation_error(
        self, 
        request: Request, 
        exc: RequestValidationError
    ) -> JSONResponse:
        """Handle FastAPI validation errors."""
        
        # Extract field errors
        field_errors = []
        for error in exc.errors():
            field_path = ".".join(str(loc) for loc in error["loc"] if loc != "body")
            field_errors.append(FieldError(
                field=field_path or "unknown",
                message=error["msg"],
                code=error["type"],
                value=error.get("input")
            ))
        
        # Log validation error
        self.logger.warning(
            "Request validation failed",
            request={
                "method": request.method,
                "path": request.url.path,
                "url": str(request.url)
            },
            validation_errors=[err.model_dump() for err in field_errors],
            event_type="validation_error"
        )
        
        # Create validation error response
        error_response = ValidationErrorResponse(
            message="Request validation failed",
            details=ErrorDetails(field_errors=field_errors),
            request_id=CorrelationIdManager.get_correlation_id()
        )
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.model_dump()
        )
    
    async def handle_http_exception(
        self, 
        request: Request, 
        exc: HTTPException
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""
        
        # Map HTTP status codes to error codes
        error_code_mapping = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.AUTHENTICATION_FAILED,
            403: ErrorCode.AUTHORIZATION_FAILED,
            404: ErrorCode.RECORD_NOT_FOUND,
            405: ErrorCode.INVALID_OPERATION,
            409: ErrorCode.RESOURCE_CONFLICT,
            422: ErrorCode.VALIDATION_ERROR,
            429: ErrorCode.RATE_LIMIT_EXCEEDED,
            500: ErrorCode.INTERNAL_SERVER_ERROR,
            502: ErrorCode.EXTERNAL_SERVICE_ERROR,
            503: ErrorCode.SERVICE_UNAVAILABLE,
            504: ErrorCode.TIMEOUT_ERROR,
        }
        
        # Map to error categories
        category_mapping = {
            400: ErrorCategory.CLIENT_ERROR,
            401: ErrorCategory.AUTHENTICATION_ERROR,
            403: ErrorCategory.AUTHORIZATION_ERROR,
            404: ErrorCategory.NOT_FOUND_ERROR,
            405: ErrorCategory.CLIENT_ERROR,
            409: ErrorCategory.CONFLICT_ERROR,
            422: ErrorCategory.VALIDATION_ERROR,
            429: ErrorCategory.CLIENT_ERROR,
            500: ErrorCategory.SERVER_ERROR,
            502: ErrorCategory.EXTERNAL_SERVICE_ERROR,
            503: ErrorCategory.SERVER_ERROR,
            504: ErrorCategory.SERVER_ERROR,
        }
        
        error_code = error_code_mapping.get(exc.status_code, ErrorCode.INTERNAL_SERVER_ERROR)
        category = category_mapping.get(exc.status_code, ErrorCategory.SERVER_ERROR)
        
        # Log HTTP exception
        log_level = "error" if exc.status_code >= 500 else "warning"
        log_method = getattr(self.logger, log_level)
        
        log_method(
            "HTTP exception occurred",
            request={
                "method": request.method,
                "path": request.url.path,
                "url": str(request.url)
            },
            error={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "error_code": error_code.value
            },
            event_type="http_exception"
        )
        
        # Create error response
        error_response = ErrorResponse(
            error_code=error_code,
            category=category,
            message=str(exc.detail),
            details=ErrorDetails(
                additional_context={"status_code": exc.status_code}
            ),
            request_id=CorrelationIdManager.get_correlation_id(),
            severity=ErrorSeverity.HIGH if exc.status_code >= 500 else ErrorSeverity.MEDIUM
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump()
        )
    
    async def handle_sqlalchemy_error(
        self, 
        request: Request, 
        exc: SQLAlchemyError
    ) -> JSONResponse:
        """Handle SQLAlchemy database errors."""
        
        # Map SQLAlchemy exceptions to custom exceptions
        if isinstance(exc, IntegrityError):
            # Check if it's a unique constraint violation
            if "duplicate key" in str(exc).lower() or "unique constraint" in str(exc).lower():
                custom_exc = DuplicateRecordException(
                    resource_type="resource",
                    cause=exc
                )
            else:
                custom_exc = DatabaseException(
                    message=f"Database integrity error: {str(exc)}",
                    error_code=ErrorCode.DATABASE_CONSTRAINT_ERROR,
                    cause=exc
                )
        elif isinstance(exc, NoResultFound):
            custom_exc = RecordNotFoundException(
                resource_type="resource",
                cause=exc
            )
        elif isinstance(exc, OperationalError):
            custom_exc = DatabaseException(
                message=f"Database operational error: {str(exc)}",
                error_code=ErrorCode.DATABASE_CONNECTION_ERROR,
                cause=exc
            )
        elif isinstance(exc, DataError):
            custom_exc = DatabaseException(
                message=f"Database data error: {str(exc)}",
                error_code=ErrorCode.DATA_INTEGRITY_ERROR,
                cause=exc
            )
        else:
            custom_exc = DatabaseException(
                message=f"Database error: {str(exc)}",
                cause=exc
            )
        
        return await self.handle_base_test_gen_exception(request, custom_exc)
    
    async def handle_general_exception(
        self, 
        request: Request, 
        exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        
        # Log the full exception with stack trace
        self.logger.error(
            "Unhandled exception occurred",
            request={
                "method": request.method,
                "path": request.url.path,
                "url": str(request.url)
            },
            error={
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc()
            },
            event_type="unhandled_exception"
        )
        
        # Create generic error response (don't expose internal details)
        error_response = ErrorResponse(
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            category=ErrorCategory.SERVER_ERROR,
            message="An internal error occurred. Please try again later.",
            details=ErrorDetails(
                additional_context={
                    "error_type": type(exc).__name__,
                    "occurred_at": request.url.path
                }
            ),
            request_id=CorrelationIdManager.get_correlation_id(),
            severity=ErrorSeverity.CRITICAL
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump()
        )
    
    async def _log_exception(self, request: Request, exc: BaseTestGenException) -> None:
        """Log exception with appropriate level and context."""
        
        # Determine log level based on error category and severity
        if exc.category in [ErrorCategory.SERVER_ERROR, ErrorCategory.EXTERNAL_SERVICE_ERROR]:
            log_level = "error"
        elif exc.category in [ErrorCategory.AUTHENTICATION_ERROR, ErrorCategory.AUTHORIZATION_ERROR]:
            log_level = "warning"
        elif exc.category in [ErrorCategory.VALIDATION_ERROR, ErrorCategory.CLIENT_ERROR]:
            log_level = "info"
        else:
            log_level = "warning"
        
        log_method = getattr(self.logger, log_level)
        
        # Create log context
        log_context = {
            "request": {
                "method": request.method,
                "path": request.url.path,
                "url": str(request.url)
            },
            "error": {
                "code": exc.error_code.value,
                "category": exc.category.value,
                "message": exc.message,
                "user_message": exc.user_message,
                "status_code": exc.status_code,
                "details": exc.details
            },
            "event_type": "application_exception"
        }
        
        # Add cause if present
        if exc.cause:
            log_context["error"]["cause"] = {
                "type": type(exc.cause).__name__,
                "message": str(exc.cause)
            }
        
        log_method(
            f"Application exception: {exc.error_code.value}",
            **log_context
        )
    
    def _create_error_details(self, exc: BaseTestGenException) -> Optional[ErrorDetails]:
        """Create error details from exception."""
        
        if not exc.details and not exc.cause:
            return None
        
        additional_context = exc.details.copy() if exc.details else {}
        
        # Add cause information if present
        if exc.cause:
            additional_context["cause"] = {
                "type": type(exc.cause).__name__,
                "message": str(exc.cause)
            }
        
        return ErrorDetails(additional_context=additional_context)
    
    def _get_error_severity(self, exc: BaseTestGenException) -> ErrorSeverity:
        """Determine error severity based on exception type and category."""
        
        # Critical errors
        if exc.error_code in [
            ErrorCode.INTERNAL_SERVER_ERROR,
            ErrorCode.DATABASE_CONNECTION_ERROR,
            ErrorCode.CONFIGURATION_ERROR
        ]:
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if exc.category in [
            ErrorCategory.SERVER_ERROR,
            ErrorCategory.EXTERNAL_SERVICE_ERROR
        ] or exc.error_code in [
            ErrorCode.AUTHENTICATION_FAILED,
            ErrorCode.AUTHORIZATION_FAILED
        ]:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if exc.category in [
            ErrorCategory.BUSINESS_LOGIC_ERROR,
            ErrorCategory.VALIDATION_ERROR,
            ErrorCategory.CONFLICT_ERROR
        ]:
            return ErrorSeverity.MEDIUM
        
        # Low severity errors
        return ErrorSeverity.LOW


# Global exception handler instance
exception_handler = GlobalExceptionHandler()


# Exception handler functions for FastAPI
async def base_test_gen_exception_handler(request: Request, exc: BaseTestGenException) -> JSONResponse:
    """Handler for custom application exceptions."""
    return await exception_handler.handle_base_test_gen_exception(request, exc)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for FastAPI validation errors."""
    return await exception_handler.handle_validation_error(request, exc)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler for FastAPI HTTP exceptions."""
    return await exception_handler.handle_http_exception(request, exc)


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handler for SQLAlchemy database errors."""
    return await exception_handler.handle_sqlalchemy_error(request, exc)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unexpected exceptions."""
    return await exception_handler.handle_general_exception(request, exc)


# Dictionary mapping exception types to handlers
EXCEPTION_HANDLERS = {
    BaseTestGenException: base_test_gen_exception_handler,
    RequestValidationError: validation_exception_handler,
    HTTPException: http_exception_handler,
    SQLAlchemyError: sqlalchemy_exception_handler,
    Exception: general_exception_handler,
}
