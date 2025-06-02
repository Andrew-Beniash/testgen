"""
Health check endpoints for the Test Generation Agent.

This module provides health check endpoints for monitoring
the application and its dependencies.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.utils.database_health import (
    quick_health_check,
    detailed_health_check,
    get_database_metrics,
    check_test_generation_health
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns:
        Dict containing basic health status
    """
    try:
        # Quick database connectivity check
        db_healthy = await quick_health_check()
        
        status = "healthy" if db_healthy else "unhealthy"
        
        return {
            "status": status,
            "service": "Test Generation Agent",
            "version": "2.0.0",
            "database": "healthy" if db_healthy else "unhealthy",
            "message": "Service is operational" if db_healthy else "Database connectivity issues"
        }
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unavailable")


@router.get("/health/detailed", tags=["health"])
async def detailed_health_check_endpoint() -> Dict[str, Any]:
    """
    Detailed health check with comprehensive diagnostics.
    
    Returns:
        Dict containing detailed health information
    """
    try:
        health_info = await detailed_health_check()
        
        if health_info["status"] != "healthy":
            raise HTTPException(status_code=503, detail=health_info)
            
        return health_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Detailed health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Health check failed")


@router.get("/health/database", tags=["health"])
async def database_health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Database-specific health check.
    
    Returns:
        Dict containing database health information
    """
    try:
        metrics = await get_database_metrics()
        
        if metrics.get("database_status") != "healthy":
            raise HTTPException(status_code=503, detail=metrics)
            
        return {
            "status": "healthy",
            "metrics": metrics,
            "message": "Database is healthy and operational"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Database health check failed")


@router.get("/health/components", tags=["health"])
async def components_health_check() -> Dict[str, Any]:
    """
    Health check for all system components.
    
    Returns:
        Dict containing health status of all components
    """
    try:
        # Database health
        db_health = await get_database_metrics()
        
        # Test generation system health
        generation_health = await check_test_generation_health()
        
        # Overall system health
        overall_healthy = (
            db_health.get("database_status") == "healthy" and
            generation_health.get("healthy", False)
        )
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "components": {
                "database": {
                    "status": db_health.get("database_status", "unknown"),
                    "metrics": db_health
                },
                "test_generation": {
                    "status": "healthy" if generation_health.get("healthy", False) else "unhealthy",
                    "metrics": generation_health
                },
                "redis": {
                    "status": "unknown",  # TODO: Implement Redis health check
                    "message": "Redis health check not yet implemented"
                },
                "vector_db": {
                    "status": "unknown",  # TODO: Implement Vector DB health check
                    "message": "Vector database health check not yet implemented"
                }
            }
        }
        
    except Exception as e:
        logger.error("Components health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Components health check failed")


@router.get("/health/readiness", tags=["health"])
async def readiness_check() -> Dict[str, Any]:
    """
    Kubernetes readiness probe endpoint.
    
    Returns:
        Dict indicating if the service is ready to accept traffic
    """
    try:
        # Check if all critical components are ready
        db_ready = await quick_health_check()
        
        # Add additional readiness checks here
        # - Redis connectivity
        # - Vector database connectivity
        # - External API availability
        
        ready = db_ready  # Extend this logic as needed
        
        if not ready:
            raise HTTPException(status_code=503, detail="Service not ready")
            
        return {
            "status": "ready",
            "message": "Service is ready to accept traffic",
            "checks": {
                "database": db_ready
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Readiness check failed")


@router.get("/health/liveness", tags=["health"])
async def liveness_check() -> Dict[str, Any]:
    """
    Kubernetes liveness probe endpoint.
    
    Returns:
        Dict indicating if the service is alive
    """
    try:
        # Basic liveness check - service is running
        return {
            "status": "alive",
            "message": "Service is alive and running"
        }
        
    except Exception as e:
        logger.error("Liveness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Liveness check failed")


@router.get("/metrics", tags=["monitoring"])
async def get_metrics() -> Dict[str, Any]:
    """
    Prometheus-compatible metrics endpoint.
    
    Returns:
        Dict containing metrics for monitoring
    """
    try:
        db_metrics = await get_database_metrics()
        generation_metrics = await check_test_generation_health()
        
        return {
            "testgen_database_connections_active": db_metrics.get("connection_count", 0),
            "testgen_database_size_mb": db_metrics.get("database_size_mb", 0),
            "testgen_database_pool_utilization": db_metrics.get("pool_utilization", 0),
            "testgen_database_errors_last_hour": db_metrics.get("error_count", 0),
            "testgen_generations_24h": generation_metrics.get("total_generations_24h", 0),
            "testgen_avg_processing_time_seconds": generation_metrics.get("avg_processing_time", 0),
            "testgen_avg_quality_score": generation_metrics.get("avg_quality_score", 0),
            "testgen_incomplete_generations": generation_metrics.get("incomplete_generations", 0),
            "timestamp": db_metrics.get("timestamp")
        }
        
    except Exception as e:
        logger.error("Metrics collection failed", error=str(e))
        raise HTTPException(status_code=503, detail="Metrics collection failed")
