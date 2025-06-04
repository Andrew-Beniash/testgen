"""
Error schema package initialization.

Exports commonly used error response schemas for easy importing.
"""

from .responses import (
    ErrorResponse,
    ValidationErrorResponse,
    AuthenticationErrorResponse,
    NotFoundErrorResponse,
    ExternalServiceErrorResponse,
    BusinessLogicErrorResponse,
    RateLimitErrorResponse,
    InternalServerErrorResponse,
    ErrorListResponse,
    AnyErrorResponse,
    ErrorDetails,
    FieldError,
    ErrorSeverity,
)

__all__ = [
    "ErrorResponse",
    "ValidationErrorResponse", 
    "AuthenticationErrorResponse",
    "NotFoundErrorResponse",
    "ExternalServiceErrorResponse",
    "BusinessLogicErrorResponse",
    "RateLimitErrorResponse",
    "InternalServerErrorResponse",
    "ErrorListResponse",
    "AnyErrorResponse",
    "ErrorDetails",
    "FieldError",
    "ErrorSeverity",
]
