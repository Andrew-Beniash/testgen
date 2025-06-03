"""
User Story model for storing Azure DevOps user story information.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List, Union
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, 
    Numeric, Enum, Boolean, TIMESTAMP, event
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Session
import enum
import json

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
    processing status, and quality metrics with enhanced functionality
    for serialization, validation, and soft delete operations.
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
    
    # Soft delete functionality
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    deleted_by = Column(String(100), nullable=True)
    
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
    
    # Additional metadata
    created_by = Column(String(100), default="system")
    updated_by = Column(String(100), default="system")
    
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

    # Computed Properties
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

    @property
    def is_active(self) -> bool:
        """Check if the user story is active (not soft deleted)."""
        return not self.is_deleted

    @property
    def total_test_cases(self) -> int:
        """Get count of associated test cases."""
        if not hasattr(self, '_test_case_count'):
            self._test_case_count = len(self.test_cases) if self.test_cases else 0
        return self._test_case_count

    @property
    def days_since_created(self) -> int:
        """Get number of days since creation."""
        if not self.created_at:
            return 0
        delta = datetime.utcnow() - self.created_at.replace(tzinfo=None)
        return delta.days

    # Serialization Methods
    def to_dict(self, include_relationships: bool = False, include_sensitive: bool = True) -> Dict[str, Any]:
        """
        Convert the user story to a dictionary representation.
        
        Args:
            include_relationships: Whether to include related objects
            include_sensitive: Whether to include sensitive/internal fields
        """
        base_dict = {
            "id": self.id,
            "azure_devops_id": self.azure_devops_id,
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "complexity_score": float(self.complexity_score) if self.complexity_score else None,
            "complexity_level": self.complexity_level,
            "domain_classification": self.domain_classification,
            "processing_status": self.processing_status.value if self.processing_status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "is_processed": self.is_processed,
            "needs_processing": self.needs_processing,
            "is_active": self.is_active,
            "total_test_cases": self.total_test_cases,
            "days_since_created": self.days_since_created
        }
        
        if include_sensitive:
            base_dict.update({
                "original_content": self.original_content,
                "normalization_metadata": self.normalization_metadata,
                "is_deleted": self.is_deleted,
                "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
                "deleted_by": self.deleted_by,
                "created_by": self.created_by,
                "updated_by": self.updated_by
            })
        
        if include_relationships:
            base_dict.update({
                "test_cases": [tc.to_dict() for tc in self.test_cases] if self.test_cases else [],
                "generation_statistics": [gs.to_dict() for gs in self.generation_statistics] if self.generation_statistics else []
            })
        
        return base_dict

    def to_json(self, **kwargs) -> str:
        """Convert to JSON string representation."""
        return json.dumps(self.to_dict(**kwargs), default=str, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserStory":
        """
        Create a UserStory instance from dictionary data.
        
        Args:
            data: Dictionary containing user story data
            
        Returns:
            UserStory instance
        """
        # Extract only valid model fields
        model_fields = {
            "azure_devops_id", "title", "description", "acceptance_criteria",
            "original_content", "normalization_metadata", "complexity_score",
            "domain_classification", "processing_status", "created_by", "updated_by"
        }
        
        filtered_data = {k: v for k, v in data.items() if k in model_fields}
        
        # Handle enum conversion
        if "processing_status" in filtered_data:
            if isinstance(filtered_data["processing_status"], str):
                filtered_data["processing_status"] = ProcessingStatus(filtered_data["processing_status"])
        
        return cls(**filtered_data)

    # Business Logic Methods
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

    def update_processing_status(self, status: ProcessingStatus, processed_at: Optional[datetime] = None, 
                               updated_by: str = "system") -> None:
        """Update the processing status and optionally set processed_at timestamp."""
        self.processing_status = status
        self.updated_by = updated_by
        if status == ProcessingStatus.COMPLETED and processed_at:
            self.processed_at = processed_at

    def update_complexity_analysis(self, complexity_score: float, domain: Optional[str] = None,
                                 normalization_metadata: Optional[Dict[str, Any]] = None,
                                 updated_by: str = "system") -> None:
        """Update complexity analysis results."""
        self.complexity_score = Decimal(str(min(1.0, max(0.0, complexity_score))))
        if domain:
            self.domain_classification = domain
        if normalization_metadata:
            self.normalization_metadata = normalization_metadata
        self.updated_by = updated_by

    def mark_for_review(self, reason: str = "Quality threshold not met", updated_by: str = "system") -> None:
        """Mark user story for human review."""
        self.processing_status = ProcessingStatus.QUEUED_FOR_REVIEW
        self.updated_by = updated_by
        
        # Add review metadata
        if not self.normalization_metadata:
            self.normalization_metadata = {}
        
        self.normalization_metadata["review_required"] = {
            "reason": reason,
            "queued_at": datetime.utcnow().isoformat(),
            "queued_by": updated_by
        }

    # Soft Delete Methods
    def soft_delete(self, deleted_by: str = "system") -> None:
        """Perform soft delete operation."""
        self.is_deleted = True
        self.deleted_at = func.now()
        self.deleted_by = deleted_by

    def restore(self, updated_by: str = "system") -> None:
        """Restore from soft delete."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.updated_by = updated_by

    # Validation Methods
    def validate_content(self) -> List[str]:
        """
        Validate user story content and return list of validation errors.
        
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Title validation
        if not self.title or len(self.title.strip()) < 10:
            errors.append("Title must be at least 10 characters long")
        
        if len(self.title) > 500:
            errors.append("Title must be less than 500 characters")
        
        # Description validation
        if not self.description or len(self.description.strip()) < 20:
            errors.append("Description must be at least 20 characters long")
        
        if len(self.description) > 5000:
            errors.append("Description must be less than 5000 characters")
        
        # Acceptance criteria validation
        if not self.acceptance_criteria or len(self.acceptance_criteria.strip()) < 10:
            errors.append("Acceptance criteria must be at least 10 characters long")
        
        if len(self.acceptance_criteria) > 3000:
            errors.append("Acceptance criteria must be less than 3000 characters")
        
        # Azure DevOps ID validation
        if not self.azure_devops_id or len(self.azure_devops_id.strip()) == 0:
            errors.append("Azure DevOps ID is required")
        
        # Complexity score validation
        if self.complexity_score is not None:
            score = float(self.complexity_score)
            if score < 0.0 or score > 1.0:
                errors.append("Complexity score must be between 0.0 and 1.0")
        
        return errors

    def is_valid(self) -> bool:
        """Check if the user story passes validation."""
        return len(self.validate_content()) == 0

    def calculate_content_hash(self) -> str:
        """Calculate hash of content for change detection."""
        import hashlib
        content = f"{self.title}|{self.description}|{self.acceptance_criteria}"
        return hashlib.md5(content.encode()).hexdigest()

    def has_content_changed(self, other_hash: str) -> bool:
        """Check if content has changed compared to provided hash."""
        return self.calculate_content_hash() != other_hash

    # Class Methods for Common Operations
    @classmethod
    def get_active_stories(cls, session: Session) -> List["UserStory"]:
        """Get all active (non-deleted) user stories."""
        return session.query(cls).filter(cls.is_deleted == False).all()

    @classmethod
    def get_pending_stories(cls, session: Session) -> List["UserStory"]:
        """Get all stories pending processing."""
        return session.query(cls).filter(
            cls.is_deleted == False,
            cls.processing_status == ProcessingStatus.PENDING
        ).all()

    @classmethod
    def get_stories_by_domain(cls, session: Session, domain: str) -> List["UserStory"]:
        """Get stories filtered by domain classification."""
        return session.query(cls).filter(
            cls.is_deleted == False,
            cls.domain_classification == domain
        ).all()

    @classmethod
    def get_stories_by_complexity(cls, session: Session, min_score: float = 0.0, 
                                max_score: float = 1.0) -> List["UserStory"]:
        """Get stories filtered by complexity score range."""
        return session.query(cls).filter(
            cls.is_deleted == False,
            cls.complexity_score.between(min_score, max_score)
        ).all()

    @classmethod
    def search_stories(cls, session: Session, search_term: str, 
                      include_deleted: bool = False) -> List["UserStory"]:
        """Search stories by title, description, or acceptance criteria."""
        query = session.query(cls)
        
        if not include_deleted:
            query = query.filter(cls.is_deleted == False)
        
        search_filter = (
            cls.title.ilike(f"%{search_term}%") |
            cls.description.ilike(f"%{search_term}%") |
            cls.acceptance_criteria.ilike(f"%{search_term}%")
        )
        
        return query.filter(search_filter).all()

    # Audit and Tracking Methods
    def create_audit_log(self) -> Dict[str, Any]:
        """Create audit log entry for changes."""
        return {
            "user_story_id": self.id,
            "azure_devops_id": self.azure_devops_id,
            "action": "update",
            "timestamp": datetime.utcnow().isoformat(),
            "updated_by": self.updated_by,
            "processing_status": self.processing_status.value if self.processing_status else None,
            "complexity_score": float(self.complexity_score) if self.complexity_score else None,
            "is_deleted": self.is_deleted
        }

    def get_processing_history(self) -> List[Dict[str, Any]]:
        """Get processing history from metadata."""
        if not self.normalization_metadata:
            return []
        
        return self.normalization_metadata.get("processing_history", [])

    def add_processing_step(self, step_name: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Add a processing step to the history."""
        if not self.normalization_metadata:
            self.normalization_metadata = {}
        
        if "processing_history" not in self.normalization_metadata:
            self.normalization_metadata["processing_history"] = []
        
        step_entry = {
            "step": step_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        
        self.normalization_metadata["processing_history"].append(step_entry)


# SQLAlchemy Event Listeners for enhanced functionality
@event.listens_for(UserStory, 'before_insert')
def before_insert_user_story(mapper, connection, target):
    """Set default values before insert."""
    if not target.created_by:
        target.created_by = "system"
    if not target.updated_by:
        target.updated_by = "system"

@event.listens_for(UserStory, 'before_update')
def before_update_user_story(mapper, connection, target):
    """Update metadata before update."""
    if not target.updated_by:
        target.updated_by = "system"
    
    # Auto-update processing history on status change
    if hasattr(target, '_processing_status_changed'):
        target.add_processing_step(
            "status_change",
            "completed",
            {"new_status": target.processing_status.value if target.processing_status else None}
        )
