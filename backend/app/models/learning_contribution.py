"""
Learning Contribution model for tracking AI system improvements.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, Numeric,
    ForeignKey, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class LearningContribution(Base):
    """
    Learning Contribution model for tracking improvements made to the AI system
    based on QA feedback and test execution results.
    
    This model enables continuous learning and improvement of the test generation system.
    """
    
    __tablename__ = "learning_contributions"
    __table_args__ = {"schema": "testgen"}

    # Primary fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_case_id = Column(
        Integer, 
        ForeignKey("testgen.test_cases.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    annotation_id = Column(
        Integer, 
        ForeignKey("testgen.qa_annotations.id", ondelete="SET NULL"), 
        nullable=True,
        index=True
    )
    
    # Learning metadata
    contribution_type = Column(
        String(50), 
        nullable=False,
        comment="Type of learning contribution (e.g., prompt_update, validation_rule, classification_improvement)"
    )
    pattern_identified = Column(
        JSONB,
        comment="Pattern or insight identified from feedback"
    )
    improvement_applied = Column(
        Text,
        comment="Description of the improvement that was applied"
    )
    quality_impact = Column(
        Numeric(3, 2),
        comment="Measured quality impact of the improvement (0-1 scale)"
    )
    
    # Technical details
    prompt_updates = Column(
        JSONB,
        comment="Details of prompt template updates applied"
    )
    model_training_data = Column(
        JSONB,
        comment="Data used for model training or fine-tuning"
    )
    validation_rule_updates = Column(
        JSONB,
        comment="Updates to validation rules based on feedback"
    )
    
    # Timestamps
    contribution_timestamp = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    applied_timestamp = Column(
        TIMESTAMP(timezone=True),
        comment="When the improvement was actually applied to the system"
    )
    effectiveness_score = Column(
        Numeric(3, 2),
        comment="Measured effectiveness of the improvement over time"
    )
    
    # Relationships
    test_case = relationship("TestCase", back_populates="learning_contributions")
    qa_annotation = relationship("QAAnnotation", back_populates="learning_contributions")

    def __repr__(self) -> str:
        return f"<LearningContribution(id={self.id}, type={self.contribution_type}, impact={self.quality_impact})>"

    def __str__(self) -> str:
        return f"Learning Contribution {self.id}: {self.contribution_type}"

    @property
    def is_applied(self) -> bool:
        """Check if the improvement has been applied to the system."""
        return self.applied_timestamp is not None

    @property
    def has_positive_impact(self) -> bool:
        """Check if the improvement has shown positive quality impact."""
        return self.quality_impact is not None and float(self.quality_impact) > 0.0

    @property
    def impact_level(self) -> str:
        """Get human-readable impact level."""
        if self.quality_impact is None:
            return "unknown"
        
        impact = float(self.quality_impact)
        if impact >= 0.2:
            return "high"
        elif impact >= 0.1:
            return "medium"
        elif impact > 0.0:
            return "low"
        else:
            return "none"

    @property
    def effectiveness_level(self) -> str:
        """Get human-readable effectiveness level."""
        if self.effectiveness_score is None:
            return "unknown"
        
        effectiveness = float(self.effectiveness_score)
        if effectiveness >= 0.8:
            return "highly_effective"
        elif effectiveness >= 0.6:
            return "effective"
        elif effectiveness >= 0.4:
            return "moderately_effective"
        else:
            return "low_effectiveness"

    @property
    def days_since_contribution(self) -> int:
        """Get number of days since the contribution was made."""
        if not self.contribution_timestamp:
            return 0
        
        delta = datetime.utcnow() - self.contribution_timestamp.replace(tzinfo=None)
        return delta.days

    @property
    def days_since_applied(self) -> Optional[int]:
        """Get number of days since the improvement was applied."""
        if not self.applied_timestamp:
            return None
        
        delta = datetime.utcnow() - self.applied_timestamp.replace(tzinfo=None)
        return delta.days

    def to_dict(self) -> Dict[str, Any]:
        """Convert the learning contribution to a dictionary representation."""
        return {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "annotation_id": self.annotation_id,
            "contribution_type": self.contribution_type,
            "pattern_identified": self.pattern_identified,
            "improvement_applied": self.improvement_applied,
            "quality_impact": float(self.quality_impact) if self.quality_impact else None,
            "impact_level": self.impact_level,
            "has_positive_impact": self.has_positive_impact,
            "prompt_updates": self.prompt_updates,
            "model_training_data": self.model_training_data,
            "validation_rule_updates": self.validation_rule_updates,
            "contribution_timestamp": self.contribution_timestamp.isoformat() if self.contribution_timestamp else None,
            "applied_timestamp": self.applied_timestamp.isoformat() if self.applied_timestamp else None,
            "is_applied": self.is_applied,
            "effectiveness_score": float(self.effectiveness_score) if self.effectiveness_score else None,
            "effectiveness_level": self.effectiveness_level,
            "days_since_contribution": self.days_since_contribution,
            "days_since_applied": self.days_since_applied
        }

    def mark_as_applied(self, applied_timestamp: Optional[datetime] = None) -> None:
        """Mark the improvement as applied to the system."""
        self.applied_timestamp = applied_timestamp or func.now()

    def update_effectiveness(self, effectiveness_score: float) -> None:
        """Update the effectiveness score based on measured results."""
        self.effectiveness_score = Decimal(str(min(1.0, max(0.0, effectiveness_score))))

    def get_prompt_updates_summary(self) -> Dict[str, Any]:
        """Get a summary of prompt updates made."""
        if not self.prompt_updates:
            return {}
        
        return {
            "templates_updated": self.prompt_updates.get("templates_updated", []),
            "parameters_changed": self.prompt_updates.get("parameters_changed", {}),
            "domains_affected": self.prompt_updates.get("domains_affected", []),
            "update_type": self.prompt_updates.get("update_type", "unknown")
        }

    def get_validation_updates_summary(self) -> Dict[str, Any]:
        """Get a summary of validation rule updates made."""
        if not self.validation_rule_updates:
            return {}
        
        return {
            "rules_added": self.validation_rule_updates.get("rules_added", []),
            "rules_modified": self.validation_rule_updates.get("rules_modified", []),
            "thresholds_changed": self.validation_rule_updates.get("thresholds_changed", {}),
            "validators_affected": self.validation_rule_updates.get("validators_affected", [])
        }

    def calculate_roi(self, cost_of_improvement: float = 1.0) -> Optional[float]:
        """
        Calculate return on investment for the improvement.
        
        Args:
            cost_of_improvement: Estimated cost of implementing the improvement
            
        Returns:
            ROI as a ratio, or None if impact cannot be calculated
        """
        if self.quality_impact is None or cost_of_improvement <= 0:
            return None
        
        # Simple ROI calculation based on quality impact
        benefit = float(self.quality_impact) * 100  # Convert to percentage benefit
        roi = (benefit - cost_of_improvement) / cost_of_improvement
        
        return roi

    @classmethod
    def create_from_feedback(cls, test_case_id: int, annotation_id: int, 
                           contribution_type: str, pattern: Dict[str, Any], 
                           improvement_description: str) -> "LearningContribution":
        """
        Factory method to create a learning contribution from QA feedback.
        
        Args:
            test_case_id: ID of the test case
            annotation_id: ID of the QA annotation
            contribution_type: Type of contribution
            pattern: Identified pattern from feedback
            improvement_description: Description of the improvement
            
        Returns:
            New LearningContribution instance
        """
        return cls(
            test_case_id=test_case_id,
            annotation_id=annotation_id,
            contribution_type=contribution_type,
            pattern_identified=pattern,
            improvement_applied=improvement_description,
            contribution_timestamp=func.now()
        )
