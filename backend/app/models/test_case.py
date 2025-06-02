"""
Test Case model for storing generated test cases.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, 
    Numeric, Enum, ForeignKey, ARRAY, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class TestClassification(str, enum.Enum):
    """Test classification enumeration."""
    MANUAL = "manual"
    API_AUTOMATION = "api_automation"
    UI_AUTOMATION = "ui_automation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    INTEGRATION = "integration"


class TestCase(Base):
    """
    Test Case model representing generated test cases for user stories.
    
    This model stores test case information including steps, classification,
    and quality metrics.
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
    
    # Test case content
    steps = Column(
        JSONB, 
        nullable=False,
        comment="Array of test steps with actions and expected results"
    )
    test_data = Column(JSONB, comment="Test data associated with the test case")
    
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
    
    # Metadata
    estimated_duration = Column(Integer, comment="Estimated duration in minutes")
    tags = Column(ARRAY(Text), comment="Tags associated with the test case")
    
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert the test case to a dictionary representation."""
        return {
            "id": self.id,
            "user_story_id": self.user_story_id,
            "azure_devops_id": self.azure_devops_id,
            "title": self.title,
            "description": self.description,
            "steps": self.steps,
            "step_count": self.step_count,
            "test_data": self.test_data,
            "has_test_data": self.has_test_data,
            "classification": self.classification.value if self.classification else None,
            "classification_confidence": float(self.classification_confidence) if self.classification_confidence else None,
            "classification_reasoning": self.classification_reasoning,
            "automation_confidence_level": self.automation_confidence_level,
            "is_automated": self.is_automated,
            "estimated_duration": self.estimated_duration,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "overall_quality_score": self.overall_quality_score
        }

    def get_step_by_number(self, step_number: int) -> Optional[Dict[str, Any]]:
        """Get a specific test step by its number."""
        if not self.steps or not isinstance(self.steps, list):
            return None
        
        for step in self.steps:
            if isinstance(step, dict) and step.get("step_number") == step_number:
                return step
        
        return None

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
        
        return errors

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
