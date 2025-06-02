"""
Quality Metrics model for tracking test case quality scores.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, Numeric, String, Boolean, 
    ForeignKey, Enum, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class ConfidenceLevel(str, enum.Enum):
    """Confidence level enumeration for quality assessments."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QualityMetrics(Base):
    """
    Quality Metrics model for storing test case quality assessments.
    
    This model tracks comprehensive quality scores across multiple dimensions
    to ensure test case quality and continuous improvement.
    """
    
    __tablename__ = "quality_metrics"
    __table_args__ = {"schema": "testgen"}

    # Primary fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_case_id = Column(
        Integer, 
        ForeignKey("testgen.test_cases.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Quality scores (0.0 to 1.0)
    overall_score = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="Overall quality score between 0 and 1"
    )
    clarity_score = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="Clarity and unambiguous language score"
    )
    completeness_score = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="Completeness of information score"
    )
    executability_score = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="Test executability without confusion score"
    )
    traceability_score = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="Connection to user story requirements score"
    )
    realism_score = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="Practical and real-world usage score"
    )
    coverage_score = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="Functionality and edge case coverage score"
    )
    
    # Quality assessment metadata
    confidence_level = Column(
        Enum(ConfidenceLevel, name="confidence_level"),
        nullable=False,
        comment="Confidence level in the quality assessment"
    )
    validation_passed = Column(
        Boolean, 
        nullable=False,
        default=False,
        comment="Whether the test case passed validation pipeline"
    )
    benchmark_percentile = Column(
        Numeric(5, 2),
        comment="Percentile ranking against benchmark dataset"
    )
    quality_issues = Column(
        JSONB,
        comment="Array of identified quality issues with details"
    )
    
    # Calculation metadata
    calculated_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    calculation_version = Column(
        String(20), 
        nullable=False,
        default="1.0",
        comment="Version of quality calculation algorithm"
    )
    
    # Relationships
    test_case = relationship("TestCase", back_populates="quality_metrics")

    def __repr__(self) -> str:
        return f"<QualityMetrics(id={self.id}, test_case_id={self.test_case_id}, overall_score={self.overall_score})>"

    def __str__(self) -> str:
        return f"Quality Metrics for Test Case {self.test_case_id}: {self.overall_score}/1.0"

    @property
    def overall_score_percentage(self) -> int:
        """Get overall score as percentage."""
        return int(float(self.overall_score) * 100) if self.overall_score else 0

    @property
    def quality_grade(self) -> str:
        """Get human-readable quality grade."""
        if self.overall_score is None:
            return "unknown"
        
        score = float(self.overall_score)
        if score >= 0.9:
            return "excellent"
        elif score >= 0.8:
            return "good"
        elif score >= 0.7:
            return "fair"
        elif score >= 0.6:
            return "poor"
        else:
            return "very_poor"

    @property
    def meets_quality_threshold(self) -> bool:
        """Check if test case meets the standard quality threshold (0.75)."""
        return self.overall_score is not None and float(self.overall_score) >= 0.75

    @property
    def quality_issues_count(self) -> int:
        """Get the number of identified quality issues."""
        if not self.quality_issues or not isinstance(self.quality_issues, list):
            return 0
        return len(self.quality_issues)

    @property
    def has_quality_issues(self) -> bool:
        """Check if there are any quality issues identified."""
        return self.quality_issues_count > 0

    @property
    def dimension_scores(self) -> Dict[str, float]:
        """Get all dimension scores as a dictionary."""
        return {
            "clarity": float(self.clarity_score) if self.clarity_score else 0.0,
            "completeness": float(self.completeness_score) if self.completeness_score else 0.0,
            "executability": float(self.executability_score) if self.executability_score else 0.0,
            "traceability": float(self.traceability_score) if self.traceability_score else 0.0,
            "realism": float(self.realism_score) if self.realism_score else 0.0,
            "coverage": float(self.coverage_score) if self.coverage_score else 0.0
        }

    @property
    def lowest_scoring_dimension(self) -> tuple[str, float]:
        """Get the dimension with the lowest score."""
        scores = self.dimension_scores
        min_dimension = min(scores, key=scores.get)
        return min_dimension, scores[min_dimension]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the quality metrics to a dictionary representation."""
        return {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "overall_score": float(self.overall_score) if self.overall_score else None,
            "overall_score_percentage": self.overall_score_percentage,
            "quality_grade": self.quality_grade,
            "meets_quality_threshold": self.meets_quality_threshold,
            "dimension_scores": self.dimension_scores,
            "clarity_score": float(self.clarity_score) if self.clarity_score else None,
            "completeness_score": float(self.completeness_score) if self.completeness_score else None,
            "executability_score": float(self.executability_score) if self.executability_score else None,
            "traceability_score": float(self.traceability_score) if self.traceability_score else None,
            "realism_score": float(self.realism_score) if self.realism_score else None,
            "coverage_score": float(self.coverage_score) if self.coverage_score else None,
            "confidence_level": self.confidence_level.value if self.confidence_level else None,
            "validation_passed": self.validation_passed,
            "benchmark_percentile": float(self.benchmark_percentile) if self.benchmark_percentile else None,
            "quality_issues": self.quality_issues,
            "quality_issues_count": self.quality_issues_count,
            "has_quality_issues": self.has_quality_issues,
            "lowest_scoring_dimension": self.lowest_scoring_dimension,
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None,
            "calculation_version": self.calculation_version
        }

    def get_quality_issues_by_type(self, issue_type: str) -> List[Dict[str, Any]]:
        """Get quality issues filtered by type."""
        if not self.quality_issues or not isinstance(self.quality_issues, list):
            return []
        
        return [
            issue for issue in self.quality_issues 
            if isinstance(issue, dict) and issue.get("type") == issue_type
        ]

    def add_quality_issue(self, issue_type: str, description: str, severity: str = "medium", 
                         dimension: Optional[str] = None) -> None:
        """Add a new quality issue."""
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

    def calculate_weighted_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate weighted overall score using custom weights.
        
        Args:
            weights: Dictionary of dimension weights. If None, uses default weights.
            
        Returns:
            Weighted overall score between 0 and 1
        """
        if weights is None:
            # Default weights from specification
            weights = {
                "clarity": 0.25,
                "completeness": 0.25,
                "executability": 0.20,
                "traceability": 0.15,
                "realism": 0.10,
                "coverage": 0.05
            }
        
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0
        
        weighted_sum = (
            float(self.clarity_score or 0) * weights.get("clarity", 0) +
            float(self.completeness_score or 0) * weights.get("completeness", 0) +
            float(self.executability_score or 0) * weights.get("executability", 0) +
            float(self.traceability_score or 0) * weights.get("traceability", 0) +
            float(self.realism_score or 0) * weights.get("realism", 0) +
            float(self.coverage_score or 0) * weights.get("coverage", 0)
        )
        
        return weighted_sum / total_weight

    def update_scores(self, scores: Dict[str, float], confidence_level: ConfidenceLevel, 
                     validation_passed: bool = True) -> None:
        """Update all quality scores and metadata."""
        self.clarity_score = Decimal(str(scores.get("clarity", 0.0)))
        self.completeness_score = Decimal(str(scores.get("completeness", 0.0)))
        self.executability_score = Decimal(str(scores.get("executability", 0.0)))
        self.traceability_score = Decimal(str(scores.get("traceability", 0.0)))
        self.realism_score = Decimal(str(scores.get("realism", 0.0)))
        self.coverage_score = Decimal(str(scores.get("coverage", 0.0)))
        
        # Calculate overall score
        self.overall_score = Decimal(str(self.calculate_weighted_score()))
        
        self.confidence_level = confidence_level
        self.validation_passed = validation_passed
        self.calculated_at = func.now()
