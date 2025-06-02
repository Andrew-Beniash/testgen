"""
System Health Log model for tracking system status and monitoring.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base


class SystemHealthLog(Base):
    """
    System Health Log model for tracking system health, status, and monitoring data.
    
    This model stores system health information for monitoring,
    alerting, and troubleshooting purposes.
    """
    
    __tablename__ = "system_health_log"
    __table_args__ = {"schema": "testgen"}

    # Primary fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    component = Column(
        String(50), 
        nullable=False,
        comment="System component being monitored (e.g., database, ai_service, webhook_processor)"
    )
    status = Column(
        String(20), 
        nullable=False,
        comment="Health status (healthy, unhealthy, warning, maintenance)"
    )
    message = Column(
        Text,
        comment="Human-readable status message or description"
    )
    metrics = Column(
        JSONB,
        comment="Detailed metrics and performance data"
    )
    timestamp = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<SystemHealthLog(id={self.id}, component={self.component}, status={self.status})>"

    def __str__(self) -> str:
        return f"Health Log {self.id}: {self.component} - {self.status}"

    @property
    def is_healthy(self) -> bool:
        """Check if the component status indicates healthy state."""
        return self.status.lower() == "healthy"

    @property
    def is_unhealthy(self) -> bool:
        """Check if the component status indicates unhealthy state."""
        return self.status.lower() == "unhealthy"

    @property
    def has_warning(self) -> bool:
        """Check if the component status indicates warning state."""
        return self.status.lower() == "warning"

    @property
    def is_maintenance(self) -> bool:
        """Check if the component is in maintenance mode."""
        return self.status.lower() == "maintenance"

    @property
    def age_in_minutes(self) -> int:
        """Get the age of this health log entry in minutes."""
        if not self.timestamp:
            return 0
        
        delta = datetime.utcnow() - self.timestamp.replace(tzinfo=None)
        return int(delta.total_seconds() / 60)

    @property
    def is_recent(self) -> bool:
        """Check if this health log entry is recent (within last 5 minutes)."""
        return self.age_in_minutes <= 5

    def to_dict(self) -> Dict[str, Any]:
        """Convert the health log to a dictionary representation."""
        return {
            "id": self.id,
            "component": self.component,
            "status": self.status,
            "message": self.message,
            "metrics": self.metrics,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "is_healthy": self.is_healthy,
            "is_unhealthy": self.is_unhealthy,
            "has_warning": self.has_warning,
            "is_maintenance": self.is_maintenance,
            "age_in_minutes": self.age_in_minutes,
            "is_recent": self.is_recent
        }

    def get_metric(self, metric_name: str, default_value: Any = None) -> Any:
        """Get a specific metric value."""
        if not self.metrics or not isinstance(self.metrics, dict):
            return default_value
        
        return self.metrics.get(metric_name, default_value)

    def has_metric(self, metric_name: str) -> bool:
        """Check if a specific metric exists."""
        return (
            self.metrics is not None and 
            isinstance(self.metrics, dict) and 
            metric_name in self.metrics
        )

    @classmethod
    def create_health_log(cls, component: str, status: str, message: Optional[str] = None, 
                         metrics: Optional[Dict[str, Any]] = None) -> "SystemHealthLog":
        """
        Factory method to create a new health log entry.
        
        Args:
            component: Name of the system component
            status: Health status
            message: Optional status message
            metrics: Optional metrics dictionary
            
        Returns:
            New SystemHealthLog instance
        """
        return cls(
            component=component,
            status=status,
            message=message,
            metrics=metrics,
            timestamp=func.now()
        )

    @classmethod
    def create_healthy_log(cls, component: str, message: Optional[str] = None, 
                          metrics: Optional[Dict[str, Any]] = None) -> "SystemHealthLog":
        """Create a healthy status log entry."""
        return cls.create_health_log(component, "healthy", message, metrics)

    @classmethod
    def create_unhealthy_log(cls, component: str, message: Optional[str] = None, 
                           metrics: Optional[Dict[str, Any]] = None) -> "SystemHealthLog":
        """Create an unhealthy status log entry."""
        return cls.create_health_log(component, "unhealthy", message, metrics)

    @classmethod
    def create_warning_log(cls, component: str, message: Optional[str] = None, 
                          metrics: Optional[Dict[str, Any]] = None) -> "SystemHealthLog":
        """Create a warning status log entry."""
        return cls.create_health_log(component, "warning", message, metrics)

    @classmethod
    def create_maintenance_log(cls, component: str, message: Optional[str] = None, 
                             metrics: Optional[Dict[str, Any]] = None) -> "SystemHealthLog":
        """Create a maintenance status log entry."""
        return cls.create_health_log(component, "maintenance", message, metrics)
