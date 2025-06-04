"""
Error response schemas for the Test Generation Agent API.

This module defines Pydantic models for standardized error responses
across all API endpoints with proper validation and documentation.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from app.core.exceptions import ErrorCode, ErrorCategory


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FieldError(BaseModel):
    """Schema for individual field validation errors."""
    
    field: str = Field(..., description="Name of the field with error")
    message: str = Field(..., description="Error message for the field")
    code: str = Field(..., description="Error code for the field")
    value: Optional[Any] = Field(None, description="The invalid value that caused the error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "field": "email",
                "message": "Invalid email format",
                "code": "INVALID_EMAIL",
                "value": "invalid-email"
            }
        }


class ErrorDetails(BaseModel):
    """Schema for additional error details and context."""
    
    resource_type: Optional[str] = Field(None, description="Type of resource involved in the error")
    resource_id: Optional[str] = Field(None, description="ID of the resource involved in the error")
    field_errors: Optional[List[FieldError]] = Field(None, description="List of field-specific errors")
    validation_errors: Optional[List[str]] = Field(None, description="List of validation error messages")
    external_service: Optional[str] = Field(None, description="Name of external service that failed")
    operation: Optional[str] = Field(None, description="Operation that was being performed")
    additional_context: Optional[Dict[str, Any]] = Field(None, description="Additional context information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "resource_type": "user_story",
                "resource_id": "123",
                "field_errors": [
                    {
                        "field": "title",
                        "message": "Title is required",
                        "code": "REQUIRED_FIELD",
                        "value": None
                    }
                ],
                "operation": "test_generation",
                "additional_context": {"attempt": 2}
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response schema for all API endpoints."""
    
    success: bool = Field(False, description="Always false for error responses")
    error_code: ErrorCode = Field(..., description="Standardized error code")
    category: ErrorCategory = Field(..., description="Error category for client handling")
    message: str = Field(..., description="User-friendly error message")
    details: Optional[ErrorDetails] = Field(None, description="Additional error details and context")
    request_id: Optional[str] = Field(None, description="Unique request identifier for tracking")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when error occurred")
    severity: ErrorSeverity = Field(ErrorSeverity.MEDIUM, description="Error severity level")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "category": "validation_error",
                "message": "The provided data is invalid. Please check and correct your input.",
                "details": {
                    "field_errors": [
                        {
                            "field": "title",
                            "message": "Title must be between 10 and 200 characters",
                            "code": "LENGTH_VALIDATION",
                            "value": "Short"
                        }
                    ]
                },
                "request_id": "req_123456789",
                "timestamp": "2024-01-15T10:30:00Z",
                "severity": "medium"
            }
        }


class ValidationErrorResponse(ErrorResponse):
    """Specialized error response for validation errors."""
    
    error_code: ErrorCode = Field(ErrorCode.VALIDATION_ERROR, description="Always validation error")
    category: ErrorCategory = Field(ErrorCategory.VALIDATION_ERROR, description="Always validation error category")
    details: ErrorDetails = Field(..., description="Must include field errors for validation failures")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "VALIDATION_ERROR",
                "category": "validation_error",
                "message": "Request validation failed",
                "details": {
                    "field_errors": [
                        {
                            "field": "acceptance_criteria",
                            "message": "Acceptance criteria must not be empty",
                            "code": "REQUIRED_FIELD",
                            "value": ""
                        },
                        {
                            "field": "complexity_score",
                            "message": "Must be between 0.0 and 1.0",
                            "code": "RANGE_VALIDATION",
                            "value": 1.5
                        }
                    ]
                },
                "request_id": "req_987654321",
                "timestamp": "2024-01-15T10:30:00Z",
                "severity": "medium"
            }
        }


class AuthenticationErrorResponse(ErrorResponse):
    """Specialized error response for authentication errors."""
    
    error_code: ErrorCode = Field(ErrorCode.AUTHENTICATION_FAILED, description="Authentication error code")
    category: ErrorCategory = Field(ErrorCategory.AUTHENTICATION_ERROR, description="Authentication error category")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "AUTHENTICATION_FAILED",
                "category": "authentication_error",
                "message": "Authentication failed. Please check your credentials.",
                "details": {
                    "operation": "token_validation"
                },
                "request_id": "req_auth_123",
                "timestamp": "2024-01-15T10:30:00Z",
                "severity": "high"
            }
        }


class NotFoundErrorResponse(ErrorResponse):
    """Specialized error response for resource not found errors."""
    
    error_code: ErrorCode = Field(ErrorCode.RECORD_NOT_FOUND, description="Not found error code")
    category: ErrorCategory = Field(ErrorCategory.NOT_FOUND_ERROR, description="Not found error category")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "RECORD_NOT_FOUND",
                "category": "not_found_error",
                "message": "The requested resource was not found.",
                "details": {
                    "resource_type": "user_story",
                    "resource_id": "123"
                },
                "request_id": "req_notfound_456",
                "timestamp": "2024-01-15T10:30:00Z",
                "severity": "medium"
            }
        }


class ExternalServiceErrorResponse(ErrorResponse):
    """Specialized error response for external service errors."""
    
    error_code: ErrorCode = Field(ErrorCode.EXTERNAL_SERVICE_ERROR, description="External service error code")
    category: ErrorCategory = Field(ErrorCategory.EXTERNAL_SERVICE_ERROR, description="External service error category")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "OPENAI_API_ERROR",
                "category": "external_service_error",
                "message": "An external service is temporarily unavailable. Please try again later.",
                "details": {
                    "external_service": "OpenAI",
                    "operation": "test_case_generation"
                },
                "request_id": "req_external_789",
                "timestamp": "2024-01-15T10:30:00Z",
                "severity": "high"
            }
        }


class BusinessLogicErrorResponse(ErrorResponse):
    """Specialized error response for business logic errors."""
    
    error_code: ErrorCode = Field(..., description="Business logic error code")
    category: ErrorCategory = Field(ErrorCategory.BUSINESS_LOGIC_ERROR, description="Business logic error category")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "QUALITY_THRESHOLD_NOT_MET",
                "category": "business_logic_error",
                "message": "The operation cannot be completed due to business rules.",
                "details": {
                    "operation": "test_case_creation",
                    "additional_context": {
                        "actual_score": 0.65,
                        "required_score": 0.75,
                        "metric_name": "overall_quality"
                    }
                },
                "request_id": "req_business_101",
                "timestamp": "2024-01-15T10:30:00Z",
                "severity": "medium"
            }
        }


class RateLimitErrorResponse(ErrorResponse):
    """Specialized error response for rate limit errors."""
    
    error_code: ErrorCode = Field(ErrorCode.RATE_LIMIT_EXCEEDED, description="Rate limit error code")
    category: ErrorCategory = Field(ErrorCategory.CLIENT_ERROR, description="Client error category")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "RATE_LIMIT_EXCEEDED",
                "category": "client_error",
                "message": "Too many requests. Please slow down and try again later.",
                "details": {
                    "additional_context": {
                        "limit": 100,
                        "window": "minute",
                        "retry_after": 60
                    }
                },
                "request_id": "req_ratelimit_202",
                "timestamp": "2024-01-15T10:30:00Z",
                "severity": "low"
            }
        }


class InternalServerErrorResponse(ErrorResponse):
    """Specialized error response for internal server errors."""
    
    error_code: ErrorCode = Field(ErrorCode.INTERNAL_SERVER_ERROR, description="Internal server error code")
    category: ErrorCategory = Field(ErrorCategory.SERVER_ERROR, description="Server error category")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "INTERNAL_SERVER_ERROR",
                "category": "server_error",
                "message": "An internal error occurred. Please try again later.",
                "details": {
                    "operation": "database_query"
                },
                "request_id": "req_internal_303",
                "timestamp": "2024-01-15T10:30:00Z",
                "severity": "critical"
            }
        }


class ErrorListResponse(BaseModel):
    """Response schema for multiple errors (used in batch operations)."""
    
    success: bool = Field(False, description="Always false for error responses")
    errors: List[ErrorResponse] = Field(..., description="List of error responses")
    summary: Dict[str, Any] = Field(..., description="Summary of errors")
    request_id: Optional[str] = Field(None, description="Unique request identifier for tracking")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when errors occurred")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "errors": [
                    {
                        "success": False,
                        "error_code": "VALIDATION_ERROR",
                        "category": "validation_error",
                        "message": "Title is required",
                        "details": {
                            "resource_id": "story_1",
                            "field_errors": [
                                {
                                    "field": "title",
                                    "message": "Title is required",
                                    "code": "REQUIRED_FIELD"
                                }
                            ]
                        }
                    }
                ],
                "summary": {
                    "total_errors": 1,
                    "validation_errors": 1,
                    "server_errors": 0
                },
                "request_id": "req_batch_404",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


# Union type for all possible error responses
AnyErrorResponse = Union[
    ErrorResponse,
    ValidationErrorResponse,
    AuthenticationErrorResponse,
    NotFoundErrorResponse,
    ExternalServiceErrorResponse,
    BusinessLogicErrorResponse,
    RateLimitErrorResponse,
    InternalServerErrorResponse,
    ErrorListResponse
]
