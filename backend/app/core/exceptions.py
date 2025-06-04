"""
Custom exception classes for the Test Generation Agent.

This module defines a hierarchy of custom exceptions with proper
error categorization, codes, and metadata for enhanced error handling.
"""

from typing import Any, Dict, Optional, List
from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes for the application."""
    
    # General application errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    
    # Authentication and authorization errors
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT_FORMAT = "INVALID_INPUT_FORMAT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"
    DATA_INTEGRITY_ERROR = "DATA_INTEGRITY_ERROR"
    
    # Database errors
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_QUERY_ERROR = "DATABASE_QUERY_ERROR"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"
    DUPLICATE_RECORD = "DUPLICATE_RECORD"
    DATABASE_CONSTRAINT_ERROR = "DATABASE_CONSTRAINT_ERROR"
    
    # External service errors
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    OPENAI_API_ERROR = "OPENAI_API_ERROR"
    AZURE_DEVOPS_ERROR = "AZURE_DEVOPS_ERROR"
    VECTOR_DB_ERROR = "VECTOR_DB_ERROR"
    REDIS_ERROR = "REDIS_ERROR"
    
    # Test generation specific errors
    GENERATION_FAILED = "GENERATION_FAILED"
    QUALITY_VALIDATION_FAILED = "QUALITY_VALIDATION_FAILED"
    CLASSIFICATION_FAILED = "CLASSIFICATION_FAILED"
    PROMPT_TEMPLATE_ERROR = "PROMPT_TEMPLATE_ERROR"
    PARSING_ERROR = "PARSING_ERROR"
    
    # Quality assurance errors
    QUALITY_THRESHOLD_NOT_MET = "QUALITY_THRESHOLD_NOT_MET"
    VALIDATION_PIPELINE_FAILED = "VALIDATION_PIPELINE_FAILED"
    BENCHMARK_COMPARISON_FAILED = "BENCHMARK_COMPARISON_FAILED"
    AUTO_FIX_FAILED = "AUTO_FIX_FAILED"
    
    # Business logic errors
    INVALID_OPERATION = "INVALID_OPERATION"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    WORKFLOW_STATE_ERROR = "WORKFLOW_STATE_ERROR"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    
    # File and data processing errors
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_PROCESSING_ERROR = "FILE_PROCESSING_ERROR"
    INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT"
    FILE_SIZE_EXCEEDED = "FILE_SIZE_EXCEEDED"


class ErrorCategory(str, Enum):
    """Error categories for grouping and handling errors."""
    
    CLIENT_ERROR = "client_error"  # 4xx errors
    SERVER_ERROR = "server_error"  # 5xx errors
    VALIDATION_ERROR = "validation_error"  # 422 errors
    AUTHENTICATION_ERROR = "authentication_error"  # 401 errors
    AUTHORIZATION_ERROR = "authorization_error"  # 403 errors
    NOT_FOUND_ERROR = "not_found_error"  # 404 errors
    CONFLICT_ERROR = "conflict_error"  # 409 errors
    EXTERNAL_SERVICE_ERROR = "external_service_error"  # External dependencies
    BUSINESS_LOGIC_ERROR = "business_logic_error"  # Domain-specific errors


class BaseTestGenException(Exception):
    """
    Base exception class for all Test Generation Agent exceptions.
    
    Provides standard structure for error handling including error codes,
    categories, HTTP status codes, and additional context.
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        category: ErrorCategory,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        user_message: Optional[str] = None,
    ):
        """
        Initialize the base exception.
        
        Args:
            message: Technical error message for logging
            error_code: Standardized error code
            category: Error category for handling
            status_code: HTTP status code
            details: Additional error context
            cause: Original exception that caused this error
            user_message: User-friendly error message
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.status_code = status_code
        self.details = details or {}
        self.cause = cause
        self.user_message = user_message or self._get_default_user_message()
    
    def _get_default_user_message(self) -> str:
        """Get default user-friendly message based on category."""
        category_messages = {
            ErrorCategory.CLIENT_ERROR: "Invalid request. Please check your input and try again.",
            ErrorCategory.SERVER_ERROR: "An internal error occurred. Please try again later.",
            ErrorCategory.VALIDATION_ERROR: "The provided data is invalid. Please check and correct your input.",
            ErrorCategory.AUTHENTICATION_ERROR: "Authentication failed. Please check your credentials.",
            ErrorCategory.AUTHORIZATION_ERROR: "You don't have permission to perform this action.",
            ErrorCategory.NOT_FOUND_ERROR: "The requested resource was not found.",
            ErrorCategory.CONFLICT_ERROR: "A conflict occurred. The resource may already exist or be in use.",
            ErrorCategory.EXTERNAL_SERVICE_ERROR: "An external service is temporarily unavailable. Please try again later.",
            ErrorCategory.BUSINESS_LOGIC_ERROR: "The operation cannot be completed due to business rules.",
        }
        return category_messages.get(self.category, "An error occurred. Please try again.")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error_code": self.error_code.value,
            "category": self.category.value,
            "message": self.user_message,
            "details": self.details,
        }
    
    def __str__(self) -> str:
        """String representation for logging."""
        return f"{self.error_code.value}: {self.message}"


# Validation Exceptions
class ValidationException(BaseTestGenException):
    """Exception for validation errors."""
    
    def __init__(
        self,
        message: str,
        field_errors: Optional[List[Dict[str, Any]]] = None,
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.VALIDATION_ERROR,
            status_code=422,
            details={"field_errors": field_errors or []},
            **kwargs
        )
        self.field_errors = field_errors or []


class InvalidInputFormatException(ValidationException):
    """Exception for invalid input format errors."""
    
    def __init__(self, message: str, field_name: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.INVALID_INPUT_FORMAT,
            details={"field_name": field_name} if field_name else {},
            **kwargs
        )


class MissingRequiredFieldException(ValidationException):
    """Exception for missing required fields."""
    
    def __init__(self, field_name: str, **kwargs):
        super().__init__(
            message=f"Required field '{field_name}' is missing",
            error_code=ErrorCode.MISSING_REQUIRED_FIELD,
            details={"field_name": field_name},
            **kwargs
        )


# Authentication and Authorization Exceptions
class AuthenticationException(BaseTestGenException):
    """Exception for authentication errors."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_FAILED,
            category=ErrorCategory.AUTHENTICATION_ERROR,
            status_code=401,
            **kwargs
        )


class AuthorizationException(BaseTestGenException):
    """Exception for authorization errors."""
    
    def __init__(self, message: str = "Authorization failed", **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHORIZATION_FAILED,
            category=ErrorCategory.AUTHORIZATION_ERROR,
            status_code=403,
            **kwargs
        )


class TokenExpiredException(AuthenticationException):
    """Exception for expired tokens."""
    
    def __init__(self, **kwargs):
        super().__init__(
            message="Authentication token has expired",
            error_code=ErrorCode.TOKEN_EXPIRED,
            **kwargs
        )


# Database Exceptions
class DatabaseException(BaseTestGenException):
    """Exception for database errors."""
    
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.DATABASE_QUERY_ERROR, **kwargs):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.SERVER_ERROR,
            status_code=500,
            **kwargs
        )


class RecordNotFoundException(DatabaseException):
    """Exception for when a database record is not found."""
    
    def __init__(self, resource_type: str, resource_id: Any = None, **kwargs):
        message = f"{resource_type} not found"
        if resource_id:
            message += f" with ID: {resource_id}"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.RECORD_NOT_FOUND,
            category=ErrorCategory.NOT_FOUND_ERROR,
            status_code=404,
            details={"resource_type": resource_type, "resource_id": str(resource_id) if resource_id else None},
            **kwargs
        )


class DuplicateRecordException(DatabaseException):
    """Exception for duplicate record errors."""
    
    def __init__(self, resource_type: str, conflicting_field: str = None, **kwargs):
        message = f"Duplicate {resource_type} found"
        if conflicting_field:
            message += f" with conflicting {conflicting_field}"
        
        super().__init__(
            message=message,
            error_code=ErrorCode.DUPLICATE_RECORD,
            category=ErrorCategory.CONFLICT_ERROR,
            status_code=409,
            details={"resource_type": resource_type, "conflicting_field": conflicting_field},
            **kwargs
        )


# External Service Exceptions
class ExternalServiceException(BaseTestGenException):
    """Exception for external service errors."""
    
    def __init__(
        self, 
        service_name: str, 
        message: str = None,
        error_code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_ERROR,
        **kwargs
    ):
        message = message or f"External service '{service_name}' is unavailable"
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.EXTERNAL_SERVICE_ERROR,
            status_code=503,
            details={"service_name": service_name},
            **kwargs
        )


class OpenAIException(ExternalServiceException):
    """Exception for OpenAI API errors."""
    
    def __init__(self, message: str = "OpenAI API error", **kwargs):
        super().__init__(
            service_name="OpenAI",
            message=message,
            error_code=ErrorCode.OPENAI_API_ERROR,
            **kwargs
        )


class AzureDevOpsException(ExternalServiceException):
    """Exception for Azure DevOps errors."""
    
    def __init__(self, message: str = "Azure DevOps API error", **kwargs):
        super().__init__(
            service_name="Azure DevOps",
            message=message,
            error_code=ErrorCode.AZURE_DEVOPS_ERROR,
            **kwargs
        )


class VectorDatabaseException(ExternalServiceException):
    """Exception for vector database errors."""
    
    def __init__(self, message: str = "Vector database error", **kwargs):
        super().__init__(
            service_name="Vector Database",
            message=message,
            error_code=ErrorCode.VECTOR_DB_ERROR,
            **kwargs
        )


# Test Generation Specific Exceptions
class TestGenerationException(BaseTestGenException):
    """Exception for test case generation errors."""
    
    def __init__(
        self, 
        message: str, 
        user_story_id: Optional[int] = None,
        error_code: ErrorCode = ErrorCode.GENERATION_FAILED,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.BUSINESS_LOGIC_ERROR,
            status_code=422,
            details={"user_story_id": user_story_id} if user_story_id else {},
            **kwargs
        )


class QualityValidationException(TestGenerationException):
    """Exception for quality validation failures."""
    
    def __init__(
        self, 
        message: str, 
        quality_score: Optional[float] = None,
        threshold: Optional[float] = None,
        validation_errors: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.QUALITY_VALIDATION_FAILED,
            details={
                "quality_score": quality_score,
                "threshold": threshold,
                "validation_errors": validation_errors or [],
            },
            **kwargs
        )


class ClassificationException(TestGenerationException):
    """Exception for test case classification errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.CLASSIFICATION_FAILED,
            **kwargs
        )


class PromptTemplateException(TestGenerationException):
    """Exception for prompt template errors."""
    
    def __init__(self, template_name: str, message: str = None, **kwargs):
        message = message or f"Prompt template '{template_name}' error"
        super().__init__(
            message=message,
            error_code=ErrorCode.PROMPT_TEMPLATE_ERROR,
            details={"template_name": template_name},
            **kwargs
        )


class ParsingException(TestGenerationException):
    """Exception for response parsing errors."""
    
    def __init__(self, message: str, raw_response: str = None, **kwargs):
        super().__init__(
            message=message,
            error_code=ErrorCode.PARSING_ERROR,
            details={"raw_response": raw_response[:500] if raw_response else None},
            **kwargs
        )


# Quality Assurance Exceptions
class QualityThresholdException(BaseTestGenException):
    """Exception for quality threshold violations."""
    
    def __init__(
        self, 
        actual_score: float, 
        required_score: float, 
        metric_name: str = "overall_quality",
        **kwargs
    ):
        message = f"Quality threshold not met: {metric_name} score {actual_score} < {required_score}"
        super().__init__(
            message=message,
            error_code=ErrorCode.QUALITY_THRESHOLD_NOT_MET,
            category=ErrorCategory.BUSINESS_LOGIC_ERROR,
            status_code=422,
            details={
                "actual_score": actual_score,
                "required_score": required_score,
                "metric_name": metric_name,
            },
            **kwargs
        )


class ValidationPipelineException(BaseTestGenException):
    """Exception for validation pipeline failures."""
    
    def __init__(self, pipeline_stage: str, message: str, **kwargs):
        super().__init__(
            message=f"Validation pipeline failed at stage '{pipeline_stage}': {message}",
            error_code=ErrorCode.VALIDATION_PIPELINE_FAILED,
            category=ErrorCategory.SERVER_ERROR,
            status_code=500,
            details={"pipeline_stage": pipeline_stage},
            **kwargs
        )


# Business Logic Exceptions
class BusinessRuleViolationException(BaseTestGenException):
    """Exception for business rule violations."""
    
    def __init__(self, rule_name: str, message: str, **kwargs):
        super().__init__(
            message=f"Business rule violation: {rule_name} - {message}",
            error_code=ErrorCode.BUSINESS_RULE_VIOLATION,
            category=ErrorCategory.BUSINESS_LOGIC_ERROR,
            status_code=422,
            details={"rule_name": rule_name},
            **kwargs
        )


class InvalidOperationException(BaseTestGenException):
    """Exception for invalid operations."""
    
    def __init__(self, operation: str, reason: str, **kwargs):
        super().__init__(
            message=f"Invalid operation '{operation}': {reason}",
            error_code=ErrorCode.INVALID_OPERATION,
            category=ErrorCategory.CLIENT_ERROR,
            status_code=400,
            details={"operation": operation, "reason": reason},
            **kwargs
        )


class ResourceConflictException(BaseTestGenException):
    """Exception for resource conflicts."""
    
    def __init__(self, resource_type: str, conflict_reason: str, **kwargs):
        super().__init__(
            message=f"Resource conflict: {resource_type} - {conflict_reason}",
            error_code=ErrorCode.RESOURCE_CONFLICT,
            category=ErrorCategory.CONFLICT_ERROR,
            status_code=409,
            details={"resource_type": resource_type, "conflict_reason": conflict_reason},
            **kwargs
        )


# System and Configuration Exceptions
class ConfigurationException(BaseTestGenException):
    """Exception for configuration errors."""
    
    def __init__(self, config_key: str, message: str, **kwargs):
        super().__init__(
            message=f"Configuration error for '{config_key}': {message}",
            error_code=ErrorCode.CONFIGURATION_ERROR,
            category=ErrorCategory.SERVER_ERROR,
            status_code=500,
            details={"config_key": config_key},
            **kwargs
        )


class RateLimitExceededException(BaseTestGenException):
    """Exception for rate limit violations."""
    
    def __init__(self, limit: int, window: str, **kwargs):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            category=ErrorCategory.CLIENT_ERROR,
            status_code=429,
            details={"limit": limit, "window": window},
            **kwargs
        )


class TimeoutException(BaseTestGenException):
    """Exception for timeout errors."""
    
    def __init__(self, operation: str, timeout_seconds: int, **kwargs):
        super().__init__(
            message=f"Operation '{operation}' timed out after {timeout_seconds} seconds",
            error_code=ErrorCode.TIMEOUT_ERROR,
            category=ErrorCategory.SERVER_ERROR,
            status_code=504,
            details={"operation": operation, "timeout_seconds": timeout_seconds},
            **kwargs
        )
