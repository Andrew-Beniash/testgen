"""
Enhanced request/response logging middleware for comprehensive API monitoring.

This module provides detailed logging of HTTP requests and responses with
configurable levels of detail, sensitive data filtering, and performance metrics.
"""

import time
import json
from typing import Callable, Dict, Any, Optional, Set, List
from fastapi import Request, Response
from fastapi.routing import APIRoute
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.utils.correlation import CorrelationIdManager, get_correlation_logger


class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for comprehensive request/response logging with security considerations.
    """
    
    # Sensitive headers that should be masked in logs
    SENSITIVE_HEADERS = {
        "authorization", "x-api-key", "x-auth-token", "cookie", 
        "x-csrf-token", "x-access-token", "x-refresh-token"
    }
    
    # Sensitive query parameters that should be masked
    SENSITIVE_QUERY_PARAMS = {
        "password", "token", "api_key", "secret", "auth"
    }
    
    # Sensitive body fields that should be masked
    SENSITIVE_BODY_FIELDS = {
        "password", "token", "api_key", "secret", "auth", "private_key",
        "access_token", "refresh_token", "client_secret"
    }
    
    # Paths to exclude from detailed logging (health checks, metrics, etc.)
    EXCLUDED_PATHS = {
        "/health", "/healthz", "/metrics", "/favicon.ico"
    }
    
    def __init__(
        self,
        app,
        *,
        log_requests: bool = True,
        log_responses: bool = True,
        log_request_body: bool = True,
        log_response_body: bool = False,  # Disabled by default for performance
        max_body_size: int = 8192,  # 8KB max body logging
        exclude_paths: Optional[Set[str]] = None,
        log_level: str = "INFO"
    ):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size
        self.exclude_paths = exclude_paths or self.EXCLUDED_PATHS
        self.logger = get_correlation_logger(__name__)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response with comprehensive logging."""
        
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Extract correlation ID and set in context
        correlation_id = CorrelationIdManager.extract_from_request(request)
        CorrelationIdManager.set_correlation_id(correlation_id)
        
        # Record start time
        start_time = time.time()
        
        # Log request
        if self.log_requests:
            await self._log_request(request)
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log error and re-raise
            processing_time = time.time() - start_time
            await self._log_error(request, exc, processing_time)
            raise
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Add correlation ID to response
        CorrelationIdManager.add_to_response(response, correlation_id)
        
        # Add performance headers
        response.headers["X-Process-Time"] = str(processing_time)
        
        # Log response
        if self.log_responses:
            await self._log_response(request, response, processing_time)
        
        return response
    
    async def _log_request(self, request: Request) -> None:
        """Log incoming request details."""
        
        # Basic request info
        request_data = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": self._mask_sensitive_params(dict(request.query_params)),
            "headers": self._mask_sensitive_headers(dict(request.headers)),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "content_type": request.headers.get("content-type", ""),
            "content_length": request.headers.get("content-length", 0),
        }
        
        # Add request body if enabled and appropriate
        if self.log_request_body and self._should_log_body(request):
            request_data["body"] = await self._get_request_body(request)
        
        self.logger.info(
            "HTTP request received",
            request=request_data,
            event_type="http_request"
        )
    
    async def _log_response(self, request: Request, response: Response, processing_time: float) -> None:
        """Log outgoing response details."""
        
        # Basic response info
        response_data = {
            "status_code": response.status_code,
            "headers": self._mask_sensitive_headers(dict(response.headers)),
            "processing_time_ms": round(processing_time * 1000, 2),
            "content_length": response.headers.get("content-length", 0),
        }
        
        # Add response body if enabled and appropriate
        if self.log_response_body and self._should_log_response_body(response):
            response_data["body"] = await self._get_response_body(response)
        
        # Determine log level based on status code
        if response.status_code >= 500:
            log_level = "error"
        elif response.status_code >= 400:
            log_level = "warning"
        else:
            log_level = "info"
        
        log_method = getattr(self.logger, log_level)
        log_method(
            "HTTP response sent",
            request={"method": request.method, "path": request.url.path},
            response=response_data,
            event_type="http_response"
        )
    
    async def _log_error(self, request: Request, exc: Exception, processing_time: float) -> None:
        """Log request processing error."""
        
        self.logger.error(
            "HTTP request processing failed",
            request={
                "method": request.method,
                "path": request.url.path,
                "url": str(request.url)
            },
            error={
                "type": type(exc).__name__,
                "message": str(exc),
                "processing_time_ms": round(processing_time * 1000, 2)
            },
            event_type="http_error"
        )
    
    def _mask_sensitive_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Mask sensitive header values."""
        masked_headers = {}
        for key, value in headers.items():
            if key.lower() in self.SENSITIVE_HEADERS:
                # Show only first few and last few characters
                if len(value) > 8:
                    masked_headers[key] = f"{value[:4]}***{value[-4:]}"
                else:
                    masked_headers[key] = "***"
            else:
                masked_headers[key] = value
        return masked_headers
    
    def _mask_sensitive_params(self, params: Dict[str, str]) -> Dict[str, str]:
        """Mask sensitive query parameter values."""
        masked_params = {}
        for key, value in params.items():
            if key.lower() in self.SENSITIVE_QUERY_PARAMS:
                masked_params[key] = "***"
            else:
                masked_params[key] = value
        return masked_params
    
    def _mask_sensitive_body_fields(self, body: Any) -> Any:
        """Recursively mask sensitive fields in request/response body."""
        if isinstance(body, dict):
            masked_body = {}
            for key, value in body.items():
                if key.lower() in self.SENSITIVE_BODY_FIELDS:
                    masked_body[key] = "***"
                elif isinstance(value, (dict, list)):
                    masked_body[key] = self._mask_sensitive_body_fields(value)
                else:
                    masked_body[key] = value
            return masked_body
        elif isinstance(body, list):
            return [self._mask_sensitive_body_fields(item) for item in body]
        else:
            return body
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded IP headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    def _should_log_body(self, request: Request) -> bool:
        """Determine if request body should be logged."""
        content_type = request.headers.get("content-type", "")
        
        # Only log certain content types
        loggable_types = [
            "application/json",
            "application/x-www-form-urlencoded", 
            "text/plain"
        ]
        
        return any(ct in content_type for ct in loggable_types)
    
    def _should_log_response_body(self, response: Response) -> bool:
        """Determine if response body should be logged."""
        content_type = response.headers.get("content-type", "")
        
        # Only log JSON responses and only for errors
        return "application/json" in content_type and response.status_code >= 400
    
    async def _get_request_body(self, request: Request) -> Optional[str]:
        """Extract and mask request body."""
        try:
            # Read body
            body = await request.body()
            
            # Check size limit
            if len(body) > self.max_body_size:
                return f"<body too large: {len(body)} bytes>"
            
            # Try to parse as JSON for masking
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    parsed_body = json.loads(body)
                    masked_body = self._mask_sensitive_body_fields(parsed_body)
                    return json.dumps(masked_body, separators=(',', ':'))
                except json.JSONDecodeError:
                    pass
            
            # Return as string for other types
            return body.decode('utf-8', errors='replace')
            
        except Exception as e:
            return f"<error reading body: {str(e)}>"
    
    async def _get_response_body(self, response: Response) -> Optional[str]:
        """Extract response body for logging (only for errors)."""
        try:
            # Only log response body for certain types and status codes
            if not hasattr(response, 'body'):
                return None
            
            if isinstance(response, StreamingResponse):
                return "<streaming response>"
            
            # Try to get body content
            if hasattr(response, 'body') and response.body:
                body = response.body
                
                # Check size limit
                if len(body) > self.max_body_size:
                    return f"<body too large: {len(body)} bytes>"
                
                # Try to parse as JSON
                try:
                    parsed_body = json.loads(body)
                    masked_body = self._mask_sensitive_body_fields(parsed_body)
                    return json.dumps(masked_body, separators=(',', ':'))
                except (json.JSONDecodeError, TypeError):
                    # Return as string
                    return body.decode('utf-8', errors='replace') if isinstance(body, bytes) else str(body)
            
            return None
            
        except Exception as e:
            return f"<error reading response body: {str(e)}>"


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for performance monitoring and slow request detection.
    """
    
    def __init__(
        self,
        app,
        *,
        slow_request_threshold: float = 1.0,  # seconds
        log_all_requests: bool = False,
        exclude_paths: Optional[Set[str]] = None
    ):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
        self.log_all_requests = log_all_requests
        self.exclude_paths = exclude_paths or {"/health", "/healthz", "/metrics"}
        self.logger = get_correlation_logger(__name__)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance."""
        
        # Skip monitoring for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            processing_time = time.time() - start_time
            
            # Log performance metrics
            await self._log_performance(request, response, processing_time)
            
            return response
            
        except Exception as exc:
            processing_time = time.time() - start_time
            
            # Log error performance
            self.logger.error(
                "Request failed with exception",
                request={
                    "method": request.method,
                    "path": request.url.path
                },
                performance={
                    "processing_time_ms": round(processing_time * 1000, 2),
                    "error": str(exc)
                },
                event_type="performance_error"
            )
            raise
    
    async def _log_performance(self, request: Request, response: Response, processing_time: float) -> None:
        """Log performance metrics."""
        
        performance_data = {
            "processing_time_ms": round(processing_time * 1000, 2),
            "status_code": response.status_code,
            "method": request.method,
            "path": request.url.path,
            "slow_request": processing_time > self.slow_request_threshold
        }
        
        # Always log slow requests
        if processing_time > self.slow_request_threshold:
            self.logger.warning(
                "Slow request detected",
                request={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params)
                },
                performance=performance_data,
                event_type="slow_request"
            )
        elif self.log_all_requests:
            # Log all requests if enabled
            self.logger.info(
                "Request performance",
                performance=performance_data,
                event_type="performance"
            )


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for security event logging and monitoring.
    """
    
    def __init__(
        self,
        app,
        *,
        log_security_events: bool = True,
        suspicious_patterns: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.log_security_events = log_security_events
        self.suspicious_patterns = suspicious_patterns or [
            "script", "alert", "javascript:", "vbscript:", "<script",
            "union select", "drop table", "delete from", "../", "..\\",
            "eval(", "exec(", "system(", "cmd.exe", "/bin/bash"
        ]
        self.logger = get_correlation_logger(__name__)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor for security events."""
        
        if self.log_security_events:
            await self._check_security_patterns(request)
        
        return await call_next(request)
    
    async def _check_security_patterns(self, request: Request) -> None:
        """Check request for suspicious patterns."""
        
        # Check URL for suspicious patterns
        url_str = str(request.url).lower()
        for pattern in self.suspicious_patterns:
            if pattern.lower() in url_str:
                self.logger.warning(
                    "Suspicious pattern detected in URL",
                    request={
                        "method": request.method,
                        "url": str(request.url),
                        "client_ip": self._get_client_ip(request)
                    },
                    security={
                        "pattern": pattern,
                        "location": "url"
                    },
                    event_type="security_alert"
                )
                break
        
        # Check headers for suspicious patterns
        for header_name, header_value in request.headers.items():
            header_value_lower = header_value.lower()
            for pattern in self.suspicious_patterns:
                if pattern.lower() in header_value_lower:
                    self.logger.warning(
                        "Suspicious pattern detected in headers",
                        request={
                            "method": request.method,
                            "path": request.url.path,
                            "client_ip": self._get_client_ip(request)
                        },
                        security={
                            "pattern": pattern,
                            "location": f"header:{header_name}",
                            "header_value": header_value[:100] + "..." if len(header_value) > 100 else header_value
                        },
                        event_type="security_alert"
                    )
                    break
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
