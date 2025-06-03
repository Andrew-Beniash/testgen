"""
Test Case model for storing generated test cases.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List, Union
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, 
    Numeric, Enum, ForeignKey, ARRAY, TIMESTAMP, Boolean, event
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Session
import enum
import json

from app.core.database import Base


class TestClassification(str, enum.Enum):
    """Test classification enumeration."""
    MANUAL = "manual"
    API_AUTOMATION = "api_automation"
    UI_AUTOMATION = "ui_automation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    INTEGRATION = "integration"


class TestPriority(str, enum.Enum):
    """Test priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestCase(Base):
    """
    Test Case model representing generated test cases for user stories.
    
    This model stores test case information including steps, classification,
    quality metrics, and provides enhanced functionality for validation,
    serialization, and soft delete operations.
    """
    
    __tablename__ = "test_cases"
    __table_args__ = {"schema": "testgen"}

    # Primary fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_story_id = Column(
        Integer, 
        ForeignKey("testgen.user_stories.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    azure_devops_id = Column(String(100), unique=True, nullable=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    
    # Test case content with enhanced structure
    steps = Column(
        JSONB, 
        nullable=False,
        comment="Array of test steps with actions and expected results"
    )
    test_data = Column(JSONB, comment="Test data associated with the test case")
    preconditions = Column(JSONB, comment="Prerequisites for test execution")
    postconditions = Column(JSONB, comment="Expected state after test execution")
    
    # Classification and automation
    classification = Column(
        Enum(TestClassification, name="test_classification"),
        nullable=True,
        index=True
    )
    classification_confidence = Column(
        Numeric(3, 2),
        comment="Confidence score for classification between 0 and 1"
    )
    classification_reasoning = Column(Text, comment="Explanation for classification")
    
    # Priority and planning
    priority = Column(
        Enum(TestPriority, name="test_priority"),
        default=TestPriority.MEDIUM,
        nullable=False
    )
    estimated_duration = Column(Integer, comment="Estimated duration in minutes")
    actual_duration = Column(Integer, comment="Actual execution duration in minutes")
    
    # Metadata and categorization
    tags = Column(ARRAY(Text), comment="Tags associated with the test case")
    test_environment = Column(String(50), comment="Target test environment")
    test_type = Column(String(50), comment="Type of test (positive, negative, edge)")
    
    # Execution tracking
    execution_count = Column(Integer, default=0, comment="Number of times executed")
    last_executed_at = Column(TIMESTAMP(timezone=True), comment="Last execution timestamp")
    success_rate = Column(Numeric(3, 2), comment="Historical success rate (0-1)")
    
    # Soft delete functionality
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    deleted_by = Column(String(100), nullable=True)
    
    # Timestamps and audit
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
    created_by = Column(String(100), default="system")
    updated_by = Column(String(100), default="system")
    
    # Relationships
    user_story = relationship("UserStory", back_populates="test_cases")
    quality_metrics = relationship(
        "QualityMetrics", 
        back_populates="test_case",
        cascade="all, delete-orphan",
        uselist=False  # One-to-one relationship for current metrics
    )
    qa_annotations = relationship(
        "QAAnnotation",
        back_populates="test_case", 
        cascade="all, delete-orphan"
    )
    learning_contributions = relationship(
        "LearningContribution",
        back_populates="test_case",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TestCase(id={self.id}, title='{self.title[:50]}...', classification={self.classification})>"

    def __str__(self) -> str:
        return f"Test Case {self.id}: {self.title}"

    # Computed Properties
    @property
    def step_count(self) -> int:
        """Get the number of test steps."""
        if not self.steps or not isinstance(self.steps, list):
            return 0
        return len(self.steps)

    @property
    def has_test_data(self) -> bool:
        """Check if the test case has associated test data."""
        return self.test_data is not None and len(self.test_data) > 0

    @property
    def has_preconditions(self) -> bool:
        """Check if the test case has preconditions."""
        return self.preconditions is not None and len(self.preconditions) > 0

    @property
    def has_postconditions(self) -> bool:
        """Check if the test case has postconditions."""
        return self.postconditions is not None and len(self.postconditions) > 0

    @property
    def is_automated(self) -> bool:
        """Check if the test case is suitable for automation."""
        automated_types = [
            TestClassification.API_AUTOMATION,
            TestClassification.UI_AUTOMATION,
            TestClassification.PERFORMANCE,
            TestClassification.INTEGRATION
        ]
        return self.classification in automated_types

    @property
    def automation_confidence_level(self) -> str:
        """Get human-readable automation confidence level."""
        if self.classification_confidence is None:
            return "unknown"
        
        confidence = float(self.classification_confidence)
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.5:
            return "medium"
        else:
            return "low"

    @property
    def overall_quality_score(self) -> Optional[float]:
        """Get the overall quality score from quality metrics."""
        if self.quality_metrics and self.quality_metrics.overall_score:
            return float(self.quality_metrics.overall_score)
        return None

    @property
    def is_active(self) -> bool:
        """Check if the test case is active (not soft deleted)."""
        return not self.is_deleted

    @property
    def priority_level(self) -> str:
        """Get human-readable priority level."""
        return self.priority.value if self.priority else "medium"

    @property
    def estimated_duration_hours(self) -> Optional[float]:
        """Get estimated duration in hours."""
        if self.estimated_duration:
            return self.estimated_duration / 60.0
        return None

    @property
    def execution_efficiency(self) -> Optional[float]:
        """Calculate execution efficiency (actual vs estimated time)."""
        if self.estimated_duration and self.actual_duration:
            return self.estimated_duration / self.actual_duration
        return None

    @property
    def days_since_created(self) -> int:
        """Get number of days since creation."""
        if not self.created_at:
            return 0
        delta = datetime.utcnow() - self.created_at.replace(tzinfo=None)
        return delta.days

    @property
    def days_since_executed(self) -> Optional[int]:
        """Get number of days since last execution."""
        if not self.last_executed_at:
            return None
        delta = datetime.utcnow() - self.last_executed_at.replace(tzinfo=None)
        return delta.days

    @property
    def needs_execution(self) -> bool:
        """Check if test case needs execution (never executed or stale)."""
        if not self.last_executed_at:
            return True
        return self.days_since_executed > 30  # Consider stale after 30 days

    # Serialization Methods
    def to_dict(self, include_relationships: bool = False, include_sensitive: bool = True,
                include_steps: bool = True) -> Dict[str, Any]:
        """
        Convert the test case to a dictionary representation.
        
        Args:
            include_relationships: Whether to include related objects
            include_sensitive: Whether to include sensitive/internal fields
            include_steps: Whether to include detailed step information
        """
        base_dict = {
            "id": self.id,
            "user_story_id": self.user_story_id,
            "azure_devops_id": self.azure_devops_id,
            "title": self.title,
            "description": self.description,
            "step_count": self.step_count,
            "has_test_data": self.has_test_data,
            "has_preconditions": self.has_preconditions,
            "has_postconditions": self.has_postconditions,
            "classification": self.classification.value if self.classification else None,
            "classification_confidence": float(self.classification_confidence) if self.classification_confidence else None,
            "classification_reasoning": self.classification_reasoning,
            "automation_confidence_level": self.automation_confidence_level,
            "is_automated": self.is_automated,
            "priority": self.priority_level,
            "estimated_duration": self.estimated_duration,
            "estimated_duration_hours": self.estimated_duration_hours,
            "actual_duration": self.actual_duration,
            "execution_efficiency": self.execution_efficiency,
            "tags": self.tags,
            "test_environment": self.test_environment,
            "test_type": self.test_type,
            "execution_count": self.execution_count,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
            "success_rate": float(self.success_rate) if self.success_rate else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "overall_quality_score": self.overall_quality_score,
            "days_since_created": self.days_since_created,
            "days_since_executed": self.days_since_executed,
            "needs_execution": self.needs_execution
        }

        if include_steps:
            base_dict.update({
                "steps": self.steps,
                "test_data": self.test_data,
                "preconditions": self.preconditions,
                "postconditions": self.postconditions
            })
        
        if include_sensitive:
            base_dict.update({
                "is_deleted": self.is_deleted,
                "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
                "deleted_by": self.deleted_by,
                "created_by": self.created_by,
                "updated_by": self.updated_by
            })
        
        if include_relationships:
            base_dict.update({
                "quality_metrics": self.quality_metrics.to_dict() if self.quality_metrics else None,
                "qa_annotations": [qa.to_dict() for qa in self.qa_annotations] if self.qa_annotations else [],
                "user_story": self.user_story.to_dict(include_relationships=False) if self.user_story else None
            })
        
        return base_dict

    def to_json(self, **kwargs) -> str:
        """Convert to JSON string representation."""
        return json.dumps(self.to_dict(**kwargs), default=str, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestCase":
        """
        Create a TestCase instance from dictionary data.
        
        Args:
            data: Dictionary containing test case data
            
        Returns:
            TestCase instance
        """
        # Extract only valid model fields
        model_fields = {
            "user_story_id", "azure_devops_id", "title", "description",
            "steps", "test_data", "preconditions", "postconditions",
            "classification", "classification_confidence", "classification_reasoning",
            "priority", "estimated_duration", "actual_duration", "tags",
            "test_environment", "test_type", "execution_count", "success_rate",
            "created_by", "updated_by"
        }
        
        filtered_data = {k: v for k, v in data.items() if k in model_fields}
        
        # Handle enum conversions
        if "classification" in filtered_data and isinstance(filtered_data["classification"], str):
            filtered_data["classification"] = TestClassification(filtered_data["classification"])
        
        if "priority" in filtered_data and isinstance(filtered_data["priority"], str):
            filtered_data["priority"] = TestPriority(filtered_data["priority"])
        
        return cls(**filtered_data)

    # Business Logic Methods
    def get_step_by_number(self, step_number: int) -> Optional[Dict[str, Any]]:
        """Get a specific test step by its number."""
        if not self.steps or not isinstance(self.steps, list):
            return None
        
        for step in self.steps:
            if isinstance(step, dict) and step.get("step_number") == step_number:
                return step
        
        return None

    def update_classification(self, classification: TestClassification, confidence: float,
                            reasoning: str, updated_by: str = "system") -> None:
        """Update test case classification with confidence and reasoning."""
        self.classification = classification
        self.classification_confidence = Decimal(str(min(1.0, max(0.0, confidence))))
        self.classification_reasoning = reasoning
        self.updated_by = updated_by

    def record_execution(self, duration_minutes: Optional[int] = None, 
                        success: bool = True, updated_by: str = "system") -> None:
        """Record a test execution with duration and success status."""
        self.execution_count = (self.execution_count or 0) + 1
        self.last_executed_at = func.now()
        
        if duration_minutes:
            self.actual_duration = duration_minutes
        
        # Update success rate
        if self.success_rate is None:
            self.success_rate = Decimal("1.0" if success else "0.0")
        else:
            current_rate = float(self.success_rate)
            total_executions = self.execution_count
            success_count = int(current_rate * (total_executions - 1))
            if success:
                success_count += 1
            self.success_rate = Decimal(str(success_count / total_executions))
        
        self.updated_by = updated_by

    def update_priority(self, priority: TestPriority, reason: str = None, 
                       updated_by: str = "system") -> None:
        """Update test case priority with optional reasoning."""
        self.priority = priority
        self.updated_by = updated_by
        
        # Add priority change to test data metadata
        if not self.test_data:
            self.test_data = {}
        
        if "priority_history" not in self.test_data:
            self.test_data["priority_history"] = []
        
        self.test_data["priority_history"].append({
            "priority": priority.value,
            "reason": reason,
            "changed_by": updated_by,
            "changed_at": datetime.utcnow().isoformat()
        })

    # Validation Methods
    def validate_steps(self) -> List[str]:
        """Validate test steps and return any validation errors."""
        errors = []
        
        if not self.steps:
            errors.append("Test case must have at least one step")
            return errors
        
        if not isinstance(self.steps, list):
            errors.append("Steps must be a list")
            return errors
        
        required_fields = ["step_number", "action", "expected_result"]
        
        for i, step in enumerate(self.steps):
            if not isinstance(step, dict):
                errors.append(f"Step {i + 1} must be a dictionary")
                continue
            
            for field in required_fields:
                if field not in step or not step[field]:
                    errors.append(f"Step {i + 1} missing required field: {field}")
            
            # Validate step number sequence
            expected_step_number = i + 1
            if step.get("step_number") != expected_step_number:
                errors.append(f"Step {i + 1} has incorrect step_number: expected {expected_step_number}, got {step.get('step_number')}")
            
            # Validate action length
            action = step.get("action", "")
            if len(action) < 5:
                errors.append(f"Step {i + 1} action must be at least 5 characters")
            
            # Validate expected result length
            expected_result = step.get("expected_result", "")
            if len(expected_result) < 5:
                errors.append(f"Step {i + 1} expected result must be at least 5 characters")
        
        return errors

    def validate_content(self) -> List[str]:
        """
        Validate all test case content and return list of validation errors.
        
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Title validation
        if not self.title or len(self.title.strip()) < 5:
            errors.append("Title must be at least 5 characters long")
        
        if len(self.title) > 200:
            errors.append("Title must be less than 200 characters")
        
        # Description validation
        if not self.description or len(self.description.strip()) < 10:
            errors.append("Description must be at least 10 characters long")
        
        if len(self.description) > 1000:
            errors.append("Description must be less than 1000 characters")
        
        # Steps validation
        step_errors = self.validate_steps()
        errors.extend(step_errors)
        
        # Estimated duration validation
        if self.estimated_duration is not None:
            if self.estimated_duration <= 0:
                errors.append("Estimated duration must be positive")
            elif self.estimated_duration > 480:  # 8 hours
                errors.append("Estimated duration should not exceed 480 minutes (8 hours)")
        
        # Classification confidence validation
        if self.classification_confidence is not None:
            confidence = float(self.classification_confidence)
            if confidence < 0.0 or confidence > 1.0:
                errors.append("Classification confidence must be between 0.0 and 1.0")
        
        # User story ID validation
        if not self.user_story_id:
            errors.append("User story ID is required")
        
        return errors

    def is_valid(self) -> bool:
        """Check if the test case passes validation."""
        return len(self.validate_content()) == 0

    def get_automation_readiness_score(self) -> float:
        """Calculate automation readiness score based on various factors."""
        score = 0.0
        factors = 0
        
        # Classification confidence
        if self.classification_confidence:
            score += float(self.classification_confidence)
            factors += 1
        
        # Step clarity (no vague language)
        if self.steps:
            clear_steps = 0
            vague_words = ["maybe", "should", "might", "probably", "some", "few"]
            
            for step in self.steps:
                if isinstance(step, dict):
                    action = step.get("action", "").lower()
                    expected = step.get("expected_result", "").lower()
                    
                    if not any(word in action or word in expected for word in vague_words):
                        clear_steps += 1
            
            if len(self.steps) > 0:
                clarity_score = clear_steps / len(self.steps)
                score += clarity_score
                factors += 1
        
        # Test data completeness
        if self.has_test_data:
            score += 0.8
        else:
            score += 0.3
        factors += 1
        
        # Quality metrics
        if self.overall_quality_score:
            score += self.overall_quality_score
            factors += 1
        
        return score / factors if factors > 0 else 0.0

    # Tag Management Methods
    def add_tag(self, tag: str) -> None:
        """Add a tag to the test case."""
        if self.tags is None:
            self.tags = []
        
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from the test case. Returns True if tag was removed."""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
            return True
        return False

    def has_tag(self, tag: str) -> bool:
        """Check if the test case has a specific tag."""
        return self.tags is not None and tag in self.tags

    def add_tags(self, tags: List[str]) -> None:
        """Add multiple tags to the test case."""
        for tag in tags:
            self.add_tag(tag)

    def get_tags_by_category(self, category: str) -> List[str]:
        """Get tags that start with a specific category prefix."""
        if not self.tags:
            return []
        
        prefix = f"{category}:"
        return [tag for tag in self.tags if tag.startswith(prefix)]

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

    # Class Methods for Common Operations
    @classmethod
    def get_active_test_cases(cls, session: Session) -> List["TestCase"]:
        """Get all active (non-deleted) test cases."""
        return session.query(cls).filter(cls.is_deleted == False).all()

    @classmethod
    def get_by_classification(cls, session: Session, classification: TestClassification) -> List["TestCase"]:
        """Get test cases by classification type."""
        return session.query(cls).filter(
            cls.is_deleted == False,
            cls.classification == classification
        ).all()

    @classmethod
    def get_by_priority(cls, session: Session, priority: TestPriority) -> List["TestCase"]:
        """Get test cases by priority level."""
        return session.query(cls).filter(
            cls.is_deleted == False,
            cls.priority == priority
        ).all()

    @classmethod
    def get_high_quality_cases(cls, session: Session, min_quality: float = 0.8) -> List["TestCase"]:
        """Get test cases with high quality scores."""
        from app.models.quality_metrics import QualityMetrics
        return session.query(cls).join(QualityMetrics).filter(
            cls.is_deleted == False,
            QualityMetrics.overall_score >= min_quality
        ).all()

    @classmethod
    def get_by_user_story(cls, session: Session, user_story_id: int) -> List["TestCase"]:
        """Get test cases for a specific user story."""
        return session.query(cls).filter(
            cls.is_deleted == False,
            cls.user_story_id == user_story_id
        ).all()

    @classmethod
    def get_automation_ready(cls, session: Session, min_confidence: float = 0.7) -> List["TestCase"]:
        """Get test cases ready for automation."""
        automated_types = [
            TestClassification.API_AUTOMATION,
            TestClassification.UI_AUTOMATION,
            TestClassification.PERFORMANCE,
            TestClassification.INTEGRATION
        ]
        
        return session.query(cls).filter(
            cls.is_deleted == False,
            cls.classification.in_(automated_types),
            cls.classification_confidence >= min_confidence
        ).all()

    @classmethod
    def search_test_cases(cls, session: Session, search_term: str, 
                         include_deleted: bool = False) -> List["TestCase"]:
        """Search test cases by title, description, or tags."""
        query = session.query(cls)
        
        if not include_deleted:
            query = query.filter(cls.is_deleted == False)
        
        search_filter = (
            cls.title.ilike(f"%{search_term}%") |
            cls.description.ilike(f"%{search_term}%") |
            cls.tags.op('?')(search_term)  # Check if tag exists in array
        )
        
        return query.filter(search_filter).all()

    # Audit and Analytics Methods
    def create_audit_log(self) -> Dict[str, Any]:
        """Create audit log entry for changes."""
        return {
            "test_case_id": self.id,
            "user_story_id": self.user_story_id,
            "azure_devops_id": self.azure_devops_id,
            "action": "update",
            "timestamp": datetime.utcnow().isoformat(),
            "updated_by": self.updated_by,
            "classification": self.classification.value if self.classification else None,
            "priority": self.priority.value if self.priority else None,
            "is_deleted": self.is_deleted,
            "execution_count": self.execution_count,
            "quality_score": self.overall_quality_score
        }

    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get execution statistics and trends."""
        return {
            "total_executions": self.execution_count or 0,
            "success_rate": float(self.success_rate) if self.success_rate else None,
            "last_executed": self.last_executed_at.isoformat() if self.last_executed_at else None,
            "days_since_execution": self.days_since_executed,
            "needs_execution": self.needs_execution,
            "estimated_duration": self.estimated_duration,
            "actual_duration": self.actual_duration,
            "execution_efficiency": self.execution_efficiency,
            "automation_readiness": self.get_automation_readiness_score()
        }

    def calculate_content_hash(self) -> str:
        """Calculate hash of content for change detection."""
        import hashlib
        content = f"{self.title}|{self.description}|{json.dumps(self.steps, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()


# SQLAlchemy Event Listeners for enhanced functionality
@event.listens_for(TestCase, 'before_insert')
def before_insert_test_case(mapper, connection, target):
    """Set default values before insert."""
    if not target.created_by:
        target.created_by = "system"
    if not target.updated_by:
        target.updated_by = "system"
    if not target.priority:
        target.priority = TestPriority.MEDIUM

@event.listens_for(TestCase, 'before_update')
def before_update_test_case(mapper, connection, target):
    """Update metadata before update."""
    if not target.updated_by:
        target.updated_by = "system"

@event.listens_for(TestCase, 'after_update')
def after_update_test_case(mapper, connection, target):
    """Handle post-update operations."""
    # Auto-tag based on classification
    if target.classification and target.tags is not None:
        classification_tag = f"classification:{target.classification.value}"
        if classification_tag not in target.tags:
            target.tags.append(classification_tag)
    
    # Auto-tag based on priority
    if target.priority and target.tags is not None:
        priority_tag = f"priority:{target.priority.value}"
        # Remove old priority tags
        target.tags = [tag for tag in target.tags if not tag.startswith("priority:")]
        target.tags.append(priority_tag)
