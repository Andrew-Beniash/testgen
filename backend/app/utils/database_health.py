"""
Database health check utilities.

This module provides utilities for checking database connectivity,
health status, and performance metrics.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
import structlog

from app.core.database import get_db_session, test_database_connection
from app.core.config import settings

logger = structlog.get_logger(__name__)


class DatabaseHealthChecker:
    """Database health checker with comprehensive diagnostics."""
    
    def __init__(self):
        self.last_check: Optional[datetime] = None
        self.last_result: Optional[Dict[str, Any]] = None
        self.check_interval = timedelta(minutes=5)
    
    async def check_health(self, force_check: bool = False) -> Dict[str, Any]:
        """
        Perform comprehensive database health check.
        
        Args:
            force_check: Force check even if recent check exists
            
        Returns:
            Dict containing health check results
        """
        now = datetime.utcnow()
        
        # Use cached result if recent check exists and not forced
        if (not force_check and 
            self.last_check and 
            self.last_result and 
            now - self.last_check < self.check_interval):
            self.last_result["cached"] = True
            return self.last_result
        
        try:
            # Basic connection test
            connection_info = await test_database_connection()
            
            # Performance metrics
            performance_metrics = await self._check_performance_metrics()
            
            # Table and schema checks
            schema_info = await self._check_schema_health()
            
            # Connection pool status
            pool_info = await self._check_pool_status()
            
            # System health log check
            health_log_info = await self._check_health_log()
            
            result = {
                "status": "healthy" if connection_info["status"] == "healthy" else "unhealthy",
                "timestamp": now.isoformat(),
                "connection": connection_info,
                "performance": performance_metrics,
                "schema": schema_info,
                "pool": pool_info,
                "health_log": health_log_info,
                "cached": False
            }
            
            self.last_check = now
            self.last_result = result
            
            logger.info("Database health check completed", status=result["status"])
            return result
            
        except Exception as e:
            error_result = {
                "status": "unhealthy",
                "timestamp": now.isoformat(),
                "error": str(e),
                "error_type": type(e).__name__,
                "cached": False
            }
            
            logger.error("Database health check failed", error=str(e))
            return error_result
    
    async def _check_performance_metrics(self) -> Dict[str, Any]:
        """Check database performance metrics."""
        try:
            async with get_db_session() as session:
                # Connection and query metrics
                metrics_query = text("""
                    SELECT 
                        count(*) as active_connections,
                        (SELECT setting FROM pg_settings WHERE name = 'max_connections') as max_connections,
                        pg_database_size(current_database()) as database_size,
                        (SELECT count(*) FROM information_schema.tables 
                         WHERE table_schema = 'testgen') as table_count,
                        current_setting('shared_buffers') as shared_buffers,
                        current_setting('effective_cache_size') as effective_cache_size
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """)
                
                result = await session.execute(metrics_query)
                row = result.fetchone()
                
                return {
                    "active_connections": row.active_connections,
                    "max_connections": int(row.max_connections),
                    "connection_usage_percent": (row.active_connections / int(row.max_connections)) * 100,
                    "database_size_bytes": row.database_size,
                    "database_size_mb": round(row.database_size / 1024 / 1024, 2),
                    "table_count": row.table_count,
                    "shared_buffers": row.shared_buffers,
                    "effective_cache_size": row.effective_cache_size
                }
                
        except Exception as e:
            logger.error("Failed to check performance metrics", error=str(e))
            return {"error": str(e)}
    
    async def _check_schema_health(self) -> Dict[str, Any]:
        """Check schema and table health."""
        try:
            async with get_db_session() as session:
                # Check for required tables
                required_tables = [
                    'user_stories', 'test_cases', 'quality_metrics',
                    'qa_annotations', 'learning_contributions',
                    'ground_truth_benchmark', 'system_health_log'
                ]
                
                table_check_query = text("""
                    SELECT table_name, 
                           (SELECT count(*) FROM information_schema.columns 
                            WHERE table_schema = 'testgen' AND table_name = t.table_name) as column_count
                    FROM information_schema.tables t
                    WHERE table_schema = 'testgen'
                    ORDER BY table_name
                """)
                
                result = await session.execute(table_check_query)
                existing_tables = {row.table_name: row.column_count for row in result}
                
                # Check indexes
                index_query = text("""
                    SELECT count(*) as index_count
                    FROM pg_indexes 
                    WHERE schemaname = 'testgen'
                """)
                
                index_result = await session.execute(index_query)
                index_count = index_result.scalar()
                
                missing_tables = [table for table in required_tables if table not in existing_tables]
                
                return {
                    "existing_tables": existing_tables,
                    "required_tables": required_tables,
                    "missing_tables": missing_tables,
                    "table_count": len(existing_tables),
                    "index_count": index_count,
                    "schema_healthy": len(missing_tables) == 0
                }
                
        except Exception as e:
            logger.error("Failed to check schema health", error=str(e))
            return {"error": str(e)}
    
    async def _check_pool_status(self) -> Dict[str, Any]:
        """Check connection pool status."""
        try:
            from app.core.database import get_engine
            
            engine = get_engine()
            pool = engine.pool
            
            return {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalidated": pool.invalidated(),
                "pool_healthy": pool.checkedout() < (pool.size() + pool.overflow()) * 0.8
            }
            
        except Exception as e:
            logger.error("Failed to check pool status", error=str(e))
            return {"error": str(e)}
    
    async def _check_health_log(self) -> Dict[str, Any]:
        """Check recent system health log entries."""
        try:
            async with get_db_session() as session:
                # Get recent health log entries
                log_query = text("""
                    SELECT component, status, message, timestamp
                    FROM testgen.system_health_log
                    WHERE timestamp > NOW() - INTERVAL '1 hour'
                    ORDER BY timestamp DESC
                    LIMIT 10
                """)
                
                result = await session.execute(log_query)
                recent_logs = [
                    {
                        "component": row.component,
                        "status": row.status,
                        "message": row.message,
                        "timestamp": row.timestamp.isoformat()
                    }
                    for row in result
                ]
                
                # Count errors in the last hour
                error_query = text("""
                    SELECT count(*) as error_count
                    FROM testgen.system_health_log
                    WHERE timestamp > NOW() - INTERVAL '1 hour'
                    AND status IN ('error', 'failed', 'unhealthy')
                """)
                
                error_result = await session.execute(error_query)
                error_count = error_result.scalar()
                
                return {
                    "recent_logs": recent_logs,
                    "error_count_last_hour": error_count,
                    "log_healthy": error_count < 5  # Arbitrary threshold
                }
                
        except Exception as e:
            logger.error("Failed to check health log", error=str(e))
            return {"error": str(e)}


# Global health checker instance
db_health_checker = DatabaseHealthChecker()


async def quick_health_check() -> bool:
    """
    Quick database health check for API endpoints.
    
    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error("Quick health check failed", error=str(e))
        return False


async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed database health check.
    
    Returns:
        Dict containing detailed health information
    """
    return await db_health_checker.check_health()


async def log_health_status(component: str, status: str, message: str, metrics: Optional[Dict] = None):
    """
    Log health status to the system health log.
    
    Args:
        component: Component name
        status: Status (healthy, unhealthy, warning)
        message: Status message
        metrics: Optional metrics data
    """
    try:
        async with get_db_session() as session:
            log_query = text("""
                INSERT INTO testgen.system_health_log (component, status, message, metrics)
                VALUES (:component, :status, :message, :metrics)
            """)
            
            await session.execute(log_query, {
                "component": component,
                "status": status,
                "message": message,
                "metrics": metrics
            })
            
    except Exception as e:
        logger.error("Failed to log health status", error=str(e))


async def cleanup_old_health_logs(days_to_keep: int = 7):
    """
    Clean up old health log entries.
    
    Args:
        days_to_keep: Number of days to keep logs
    """
    try:
        async with get_db_session() as session:
            cleanup_query = text("""
                DELETE FROM testgen.system_health_log
                WHERE timestamp < NOW() - INTERVAL '%s days'
            """ % days_to_keep)
            
            result = await session.execute(cleanup_query)
            deleted_count = result.rowcount
            
            logger.info("Cleaned up old health logs", deleted_count=deleted_count)
            
    except Exception as e:
        logger.error("Failed to cleanup health logs", error=str(e))


# Health check utilities for specific components
async def check_test_generation_health() -> Dict[str, Any]:
    """Check health of test generation system."""
    try:
        async with get_db_session() as session:
            # Check recent generation statistics
            stats_query = text("""
                SELECT 
                    count(*) as total_generations,
                    avg(processing_time_seconds) as avg_processing_time,
                    avg(average_quality_score) as avg_quality_score,
                    count(*) FILTER (WHERE generation_end IS NULL) as incomplete_generations
                FROM testgen.generation_statistics
                WHERE generation_start > NOW() - INTERVAL '24 hours'
            """)
            
            result = await session.execute(stats_query)
            row = result.fetchone()
            
            return {
                "total_generations_24h": row.total_generations,
                "avg_processing_time": float(row.avg_processing_time) if row.avg_processing_time else 0,
                "avg_quality_score": float(row.avg_quality_score) if row.avg_quality_score else 0,
                "incomplete_generations": row.incomplete_generations,
                "healthy": row.incomplete_generations < 5 and (row.avg_quality_score or 0) > 0.7
            }
            
    except Exception as e:
        logger.error("Failed to check test generation health", error=str(e))
        return {"error": str(e), "healthy": False}


# Monitoring utilities
async def get_database_metrics() -> Dict[str, Any]:
    """Get comprehensive database metrics for monitoring."""
    health_info = await detailed_health_check()
    
    return {
        "database_status": health_info.get("status"),
        "connection_count": health_info.get("performance", {}).get("active_connections", 0),
        "database_size_mb": health_info.get("performance", {}).get("database_size_mb", 0),
        "pool_utilization": health_info.get("pool", {}).get("checked_out", 0),
        "error_count": health_info.get("health_log", {}).get("error_count_last_hour", 0),
        "timestamp": datetime.utcnow().isoformat()
    }
