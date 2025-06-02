"""
User Story model for storing Azure DevOps user story information.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, 
    Numeric, Enum, Boolean, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class ProcessingStatus(str, enum.Enum):
    """Processing status enumeration for user stories."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUEUED_FOR_REVIEW = "queued_for_review"


class UserStory(Base):
    """
    User Story model representing Azure DevOps user stories.
    
    This model stores user story information including content,
    processing status, and quality metrics.
    """
    
    __tablename__ = "user_stories"
    __table_args__ = {"schema": "testgen"}

    # Primary fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    azure_devops_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    acceptance_criteria = Column(Text, nullable=False)
    
    # Enhanced fields for v2.0
    original_content = Column(JSONB, comment="Store original content before normalization")
    normalization_metadata = Column(JSONB, comment="Metadata about content normalization")
    complexity_score = Column(
        Numeric(3, 2), 
        comment="Complexity score between 0 and 1"
    )
    domain_classification = Column(String(50), comment="Detected domain (e.g., ecommerce, finance)")
    
    # Processing status and timestamps
    processing_status = Column(
        Enum(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.PENDING,
        nullable=False
    )
    created_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    processed_at = Column(TIMESTAMP(timezone=True))
    
    # Relationships
    test_cases = relationship(
        "TestCase", 
        back_populates="user_story",
        cascade="all, delete-orphan",
        lazy="select"
    )
    generation_statistics = relationship(
        "GenerationStatistics",
        back_populates="user_story",
        cascade="all, delete-orphan"
    )
    ground_truth_benchmarks = relationship(
        "GroundTruthBenchmark",
        back_populates="user_story",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UserStory(id={self.id}, azure_devops_id='{self.azure_devops_id}', title='{self.title[:50]}...')>"

    def __str__(self) -> str:
        return f"User Story {self.azure_devops_id}: {self.title}"

    @property
    def is_processed(self) -> bool:
        """Check if the user story has been processed."""
        return self.processing_status == ProcessingStatus.COMPLETED

    @property
    def needs_processing(self) -> bool:
        """Check if the user story needs processing."""
        return self.processing_status in [ProcessingStatus.PENDING, ProcessingStatus.FAILED]

    @property
    def complexity_level(self) -> str:
        """Get human-readable complexity level."""
        if self.complexity_score is None:
            return "unknown"
        
        score = float(self.complexity_score)
        if score < 0.3:
            return "simple"
        elif score < 0.7:
            return "medium"
        else:
            return "complex"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the user story to a dictionary representation."""
        return {
            "id": self.id,
            "azure_devops_id": self.azure_devops_id,
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "original_content": self.original_content,
            "normalization_metadata": self.normalization_metadata,
            "complexity_score": float(self.complexity_score) if self.complexity_score else None,
            "complexity_level": self.complexity_level,
            "domain_classification": self.domain_classification,
            "processing_status": self.processing_status.value if self.processing_status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "is_processed": self.is_processed,
            "needs_processing": self.needs_processing
        }

    def get_normalized_content(self) -> Dict[str, str]:
        """Get the normalized content with fallback to original."""
        if self.normalization_metadata and "normalized_content" in self.normalization_metadata:
            return self.normalization_metadata["normalized_content"]
        
        # Fallback to original content
        return {
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria
        }

    def update_processing_status(self, status: ProcessingStatus, processed_at: Optional[datetime] = None) -> None:
        """Update the processing status and optionally set processed_at timestamp."""
        self.processing_status = status
        if status == ProcessingStatus.COMPLETED and processed_at:
            self.processed_at = processed_at
