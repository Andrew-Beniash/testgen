"""
Main FastAPI application for the Test Generation Agent.

This module initializes the FastAPI application with comprehensive error handling,
enhanced logging, correlation tracking, and all necessary configurations.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
import structlog
import time

from app.core.config import settings
from app.core.database import init_database, close_db_connection
from app.utils.enhanced_logging import setup_logging
from app.utils.database_health import log_health_status
from app.utils.correlation import CorrelationIdManager, get_correlation_logger
from app.utils.request_logging import (
    RequestResponseLoggingMiddleware,
    PerformanceLoggingMiddleware,
    SecurityLoggingMiddleware
)
from app.core.exception_handler import (
    EXCEPTION_HANDLERS,
    base_test_gen_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    sqlalchemy_exception_handler,
    general_exception_handler
)
from app.core.exceptions import BaseTestGenException
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.api import api_router


# Set up enhanced logging
setup_logging()
logger = get_correlation_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events with comprehensive error handling and logging.
    
    Handles startup and shutdown tasks for the application with proper
    error handling and health status logging.
    """
    # Startup
    logger.info(
        "Starting Test Generation Agent",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        debug_mode=settings.DEBUG
    )
    
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized successfully")
        
        # Log successful startup
        await log_health_status(
            component="application_startup",
            status="healthy",
            message="Application started successfully",
            metrics={
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "debug_mode": settings.DEBUG,
                "log_level": settings.LOG_LEVEL
            }
        )
        
        # Initialize additional services here (Redis, vector DB, etc.)
        logger.info("All services initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(
            "Failed to initialize application",
            error=str(e),
            error_type=type(e).__name__,
            event_type="startup_failure"
        )
        
        # Log startup failure
        await log_health_status(
            component="application_startup",
            status="unhealthy",
            message=f"Application startup failed: {str(e)}",
            metrics={"error_type": type(e).__name__}
        )
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Test Generation Agent")
        try:
            await close_db_connection()
            logger.info("Database connections closed successfully")
        except Exception as e:
            logger.error(
                "Error during shutdown",
                error=str(e),
                error_type=type(e).__name__
            )


# Create FastAPI application with enhanced configuration
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered test case generation with comprehensive quality assurance and error handling",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
    # Enhanced exception handling
    debug=settings.DEBUG,
)

# Add enhanced middleware stack
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

# Add comprehensive logging middleware
app.add_middleware(
    RequestResponseLoggingMiddleware,
    log_requests=True,
    log_responses=True,
    log_request_body=settings.DEBUG,  # Only log bodies in debug mode
    log_response_body=False,  # Only for errors
    max_body_size=8192,
    exclude_paths={"/health", "/healthz", "/metrics", "/favicon.ico"}
)

# Add performance monitoring middleware
app.add_middleware(
    PerformanceLoggingMiddleware,
    slow_request_threshold=2.0,  # 2 seconds
    log_all_requests=settings.DEBUG,
    exclude_paths={"/health", "/healthz", "/metrics"}
)

# Add security monitoring middleware
app.add_middleware(
    SecurityLoggingMiddleware,
    log_security_events=True
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """
    Enhanced correlation ID middleware with comprehensive request tracking.
    
    Extracts or generates correlation IDs and sets up proper logging context
    for the entire request lifecycle.
    """
    # Extract or generate correlation ID
    correlation_id = CorrelationIdManager.extract_from_request(request)
    
    # Set correlation ID in context
    CorrelationIdManager.set_correlation_id(correlation_id)
    
    # Store in request state for easy access
    request.state.correlation_id = correlation_id
    
    # Add to structlog context
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        request_method=request.method,
        request_path=request.url.path
    )
    
    try:
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        CorrelationIdManager.add_to_response(response, correlation_id)
        
        return response
    
    except Exception as exc:
        # Log error with correlation context
        logger.error(
            "Request processing failed in correlation middleware",
            error=str(exc),
            error_type=type(exc).__name__,
            correlation_id=correlation_id
        )
        raise
    finally:
        # Clear correlation context
        structlog.contextvars.clear_contextvars()


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """
    Enhanced timing middleware with detailed performance metrics.
    
    Tracks request processing time and adds performance headers
    with comprehensive timing information.
    """
    start_time = time.perf_counter()
    
    try:
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.perf_counter() - start_time
        
        # Add timing headers
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        response.headers["X-Process-Time-Ms"] = f"{process_time * 1000:.2f}"
        
        # Log performance metrics
        if hasattr(request.state, 'correlation_id'):
            logger.info(
                "Request timing",
                processing_time_seconds=process_time,
                processing_time_ms=round(process_time * 1000, 2),
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                event_type="performance_metric"
            )
        
        return response
    
    except Exception as exc:
        # Log error with timing information
        process_time = time.perf_counter() - start_time
        logger.error(
            "Request failed during processing",
            processing_time_seconds=process_time,
            error=str(exc),
            error_type=type(exc).__name__,
            method=request.method,
            path=request.url.path
        )
        raise


# Register comprehensive exception handlers
app.add_exception_handler(BaseTestGenException, base_test_gen_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


@app.get("/health")
async def health_check():
    """
    Enhanced health check endpoint with comprehensive system status.
    
    Returns detailed health information including version, environment,
    and basic system status for monitoring and load balancing.
    """
    correlation_id = CorrelationIdManager.get_correlation_id()
    
    health_data = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
        "correlation_id": correlation_id,
        "services": {
            "database": "healthy",  # Could add actual DB health check
            "logging": "healthy",
            "correlation_tracking": "healthy"
        }
    }
    
    logger.debug(
        "Health check requested",
        health_status=health_data,
        event_type="health_check"
    )
    
    return health_data


@app.get("/")
async def root():
    """
    Enhanced root endpoint with comprehensive API information.
    
    Provides detailed information about the API including version,
    documentation links, and basic usage information.
    """
    correlation_id = CorrelationIdManager.get_correlation_id()
    
    api_info = {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "documentation": {
            "swagger_ui": f"{settings.API_V1_STR}/docs",
            "redoc": f"{settings.API_V1_STR}/redoc",
            "openapi_schema": f"{settings.API_V1_STR}/openapi.json"
        },
        "api_prefix": settings.API_V1_STR,
        "correlation_id": correlation_id,
        "features": [
            "AI-powered test case generation",
            "Quality assurance validation",
            "Comprehensive error handling",
            "Request correlation tracking",
            "Performance monitoring",
            "Security event logging"
        ]
    }
    
    logger.info(
        "Root endpoint accessed",
        api_info=api_info,
        event_type="api_access"
    )
    
    return api_info


# Include API routers
app.include_router(
    health_router,
    prefix="",
    tags=["health"],
    responses={
        200: {"description": "Health check successful"},
        503: {"description": "Service unavailable"}
    }
)

app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"}
    }
)


if __name__ == "__main__":
    import uvicorn
    
    # Enhanced uvicorn configuration
    uvicorn_config = {
        "host": "0.0.0.0",
        "port": 8000,
        "reload": settings.DEBUG,
        "log_level": settings.LOG_LEVEL.lower(),
        "access_log": True,
        "use_colors": True,
        "reload_includes": ["*.py"] if settings.DEBUG else None,
        "reload_excludes": ["tests/*", "*.pyc", "__pycache__/*"] if settings.DEBUG else None,
    }
    
    logger.info(
        "Starting uvicorn server",
        config=uvicorn_config,
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION
    )
    
    uvicorn.run(
        "app.main:app",
        **uvicorn_config
    )
