"""
QA Annotation model for storing human feedback on test cases.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    ForeignKey, ARRAY, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.test_case import TestClassification


class QAAnnotation(Base):
    """
    QA Annotation model for storing human feedback and annotations on test cases.
    
    This model captures QA team feedback to improve the quality of generated
    test cases and enable continuous learning.
    """
    
    __tablename__ = "qa_annotations"
    __table_args__ = {"schema": "testgen"}

    # Primary fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_case_id = Column(
        Integer, 
        ForeignKey("testgen.test_cases.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    annotator_id = Column(String(100), nullable=False, comment="ID of the QA engineer providing feedback")
    
    # Overall quality assessment
    overall_quality_rating = Column(
        Integer,
        comment="Overall quality rating from 1 (poor) to 5 (excellent)"
    )
    
    # Structured feedback
    quality_issues = Column(
        JSONB,
        comment="Structured quality issues identified by the annotator"
    )
    positive_aspects = Column(
        ARRAY(Text),
        comment="Positive aspects noted by the annotator"
    )
    
    # Dimension-specific feedback
    clarity_feedback = Column(Text, comment="Feedback on test case clarity")
    completeness_feedback = Column(Text, comment="Feedback on test case completeness")
    executability_feedback = Column(Text, comment="Feedback on test case executability")
    improvement_suggestions = Column(
        JSONB,
        comment="Structured improvement suggestions"
    )
    
    # Classification feedback
    suggested_classification = Column(
        String(50),  # Using string instead of enum to allow flexibility
        comment="Suggested classification if current one is incorrect"
    )
    classification_reasoning = Column(
        Text,
        comment="Reasoning for classification suggestion"
    )
    
    # Execution feedback
    execution_difficulty = Column(
        String(20),
        comment="Reported execution difficulty (easy, medium, hard, impossible)"
    )
    execution_time_actual = Column(
        Integer,
        comment="Actual execution time in minutes"
    )
    execution_issues = Column(
        ARRAY(Text),
        comment="Issues encountered during test execution"
    )
    
    # Processing metadata
    annotation_timestamp = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    is_processed = Column(
        Boolean,
        default=False,
        comment="Whether this annotation has been processed by the learning system"
    )
    processing_timestamp = Column(
        TIMESTAMP(timezone=True),
        comment="When this annotation was processed"
    )
    
    # Relationships
    test_case = relationship("TestCase", back_populates="qa_annotations")
    learning_contributions = relationship(
        "LearningContribution",
        back_populates="qa_annotation",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<QAAnnotation(id={self.id}, test_case_id={self.test_case_id}, rating={self.overall_quality_rating})>"

    def __str__(self) -> str:
        return f"QA Annotation {self.id} for Test Case {self.test_case_id}"

    @property
    def quality_rating_text(self) -> str:
        """Get human-readable quality rating."""
        if self.overall_quality_rating is None:
            return "not_rated"
        
        rating_map = {
            1: "poor",
            2: "fair", 
            3: "good",
            4: "very_good",
            5: "excellent"
        }
        return rating_map.get(self.overall_quality_rating, "unknown")

    @property
    def has_quality_issues(self) -> bool:
        """Check if any quality issues were identified."""
        return (
            self.quality_issues is not None and 
            len(self.quality_issues) > 0
        )

    @property
    def quality_issues_count(self) -> int:
        """Get the number of quality issues identified."""
        if not self.quality_issues or not isinstance(self.quality_issues, list):
            return 0
        return len(self.quality_issues)

    @property
    def has_improvement_suggestions(self) -> bool:
        """Check if improvement suggestions were provided."""
        return (
            self.improvement_suggestions is not None and 
            len(self.improvement_suggestions) > 0
        )

    @property
    def suggests_classification_change(self) -> bool:
        """Check if a different classification was suggested."""
        return self.suggested_classification is not None

    @property
    def execution_was_difficult(self) -> bool:
        """Check if execution was reported as difficult or impossible."""
        return self.execution_difficulty in ["hard", "impossible"]

    @property
    def has_execution_issues(self) -> bool:
        """Check if execution issues were reported."""
        return (
            self.execution_issues is not None and 
            len(self.execution_issues) > 0
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the annotation to a dictionary representation."""
        return {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "annotator_id": self.annotator_id,
            "overall_quality_rating": self.overall_quality_rating,
            "quality_rating_text": self.quality_rating_text,
            "quality_issues": self.quality_issues,
            "quality_issues_count": self.quality_issues_count,
            "has_quality_issues": self.has_quality_issues,
            "positive_aspects": self.positive_aspects,
            "clarity_feedback": self.clarity_feedback,
            "completeness_feedback": self.completeness_feedback,
            "executability_feedback": self.executability_feedback,
            "improvement_suggestions": self.improvement_suggestions,
            "has_improvement_suggestions": self.has_improvement_suggestions,
            "suggested_classification": self.suggested_classification,
            "classification_reasoning": self.classification_reasoning,
            "suggests_classification_change": self.suggests_classification_change,
            "execution_difficulty": self.execution_difficulty,
            "execution_time_actual": self.execution_time_actual,
            "execution_was_difficult": self.execution_was_difficult,
            "execution_issues": self.execution_issues,
            "has_execution_issues": self.has_execution_issues,
            "annotation_timestamp": self.annotation_timestamp.isoformat() if self.annotation_timestamp else None,
            "is_processed": self.is_processed,
            "processing_timestamp": self.processing_timestamp.isoformat() if self.processing_timestamp else None
        }

    def get_quality_issues_by_severity(self, severity: str) -> List[Dict[str, Any]]:
        """Get quality issues filtered by severity level."""
        if not self.quality_issues or not isinstance(self.quality_issues, list):
            return []
        
        return [
            issue for issue in self.quality_issues 
            if isinstance(issue, dict) and issue.get("severity") == severity
        ]

    def get_critical_quality_issues(self) -> List[Dict[str, Any]]:
        """Get only critical quality issues."""
        return self.get_quality_issues_by_severity("critical")

    def add_quality_issue(self, issue_type: str, description: str, 
                         severity: str = "medium", dimension: Optional[str] = None) -> None:
        """Add a new quality issue to the annotation."""
        if self.quality_issues is None:
            self.quality_issues = []
        
        issue = {
            "type": issue_type,
            "description": description,
            "severity": severity,
            "dimension": dimension,
            "identified_at": datetime.utcnow().isoformat()
        }
        
        self.quality_issues.append(issue)

    def add_improvement_suggestion(self, category: str, suggestion: str, 
                                 priority: str = "medium") -> None:
        """Add an improvement suggestion to the annotation."""
        if self.improvement_suggestions is None:
            self.improvement_suggestions = []
        
        suggestion_item = {
            "category": category,
            "suggestion": suggestion,
            "priority": priority,
            "suggested_at": datetime.utcnow().isoformat()
        }
        
        self.improvement_suggestions.append(suggestion_item)

    def mark_as_processed(self, processing_timestamp: Optional[datetime] = None) -> None:
        """Mark the annotation as processed by the learning system."""
        self.is_processed = True
        self.processing_timestamp = processing_timestamp or func.now()

    def calculate_feedback_sentiment(self) -> str:
        """Calculate overall sentiment of the feedback (positive, neutral, negative)."""
        if self.overall_quality_rating is None:
            return "neutral"
        
        # Count positive vs negative indicators
        positive_score = 0
        negative_score = 0
        
        # Rating contribution
        if self.overall_quality_rating >= 4:
            positive_score += 2
        elif self.overall_quality_rating <= 2:
            negative_score += 2
        
        # Positive aspects contribution
        if self.positive_aspects and len(self.positive_aspects) > 0:
            positive_score += len(self.positive_aspects)
        
        # Quality issues contribution
        if self.has_quality_issues:
            negative_score += self.quality_issues_count
        
        # Execution difficulty contribution
        if self.execution_was_difficult:
            negative_score += 1
        
        # Execution issues contribution
        if self.has_execution_issues:
            negative_score += len(self.execution_issues)
        
        # Determine sentiment
        if positive_score > negative_score:
            return "positive"
        elif negative_score > positive_score:
            return "negative"
        else:
            return "neutral"

    def get_learning_insights(self) -> Dict[str, Any]:
        """Extract key insights for the learning system."""
        return {
            "quality_rating": self.overall_quality_rating,
            "sentiment": self.calculate_feedback_sentiment(),
            "critical_issues": self.get_critical_quality_issues(),
            "improvement_areas": [
                issue.get("dimension") for issue in (self.quality_issues or [])
                if isinstance(issue, dict) and issue.get("dimension")
            ],
            "classification_feedback": {
                "suggested_classification": self.suggested_classification,
                "reasoning": self.classification_reasoning
            } if self.suggests_classification_change else None,
            "execution_feedback": {
                "difficulty": self.execution_difficulty,
                "time_actual": self.execution_time_actual,
                "issues": self.execution_issues
            } if self.execution_difficulty else None
        }
