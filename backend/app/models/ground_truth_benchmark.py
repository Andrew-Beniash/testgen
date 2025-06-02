"""
Ground Truth Benchmark model for quality measurement reference data.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric,
    ForeignKey, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class GroundTruthBenchmark(Base):
    """
    Ground Truth Benchmark model for storing expert-reviewed test cases
    used as quality measurement reference data.
    
    This model maintains a curated dataset of high-quality examples
    for measuring and improving system performance.
    """
    
    __tablename__ = "ground_truth_benchmark"
    __table_args__ = {"schema": "testgen"}

    # Primary fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_story_id = Column(
        Integer, 
        ForeignKey("testgen.user_stories.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Benchmark content
    benchmark_story_content = Column(
        JSONB, 
        nullable=False,
        comment="Complete user story content used for benchmarking"
    )
    expert_test_cases = Column(
        JSONB, 
        nullable=False,
        comment="Expert-created test cases for this user story"
    )
    
    # Classification metadata
    domain = Column(
        String(50), 
        nullable=False,
        comment="Domain classification (e.g., ecommerce, finance, healthcare)"
    )
    complexity_level = Column(
        String(20), 
        nullable=False,
        comment="Complexity level (simple, medium, complex)"
    )
    
    # Review metadata
    reviewer_id = Column(
        String(100), 
        nullable=False,
        comment="ID of the expert who reviewed and approved this benchmark"
    )
    reviewer_experience_level = Column(
        String(20), 
        nullable=False,
        comment="Experience level of the reviewer (junior, senior, expert)"
    )
    
    # Quality scores
    quality_rating = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="Expert quality rating for the benchmark (0-1 scale)"
    )
    coverage_completeness = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="How completely the test cases cover the user story (0-1 scale)"
    )
    
    # Benchmark lifecycle
    benchmark_creation_date = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    last_validation_date = Column(
        TIMESTAMP(timezone=True),
        comment="Last time this benchmark was validated for continued relevance"
    )
    is_active = Column(
        Boolean, 
        default=True,
        comment="Whether this benchmark is currently active and being used"
    )
    usage_count = Column(
        Integer, 
        default=0,
        comment="Number of times this benchmark has been used for comparison"
    )
    
    # Relationships
    user_story = relationship("UserStory", back_populates="ground_truth_benchmarks")

    def __repr__(self) -> str:
        return f"<GroundTruthBenchmark(id={self.id}, domain={self.domain}, quality_rating={self.quality_rating})>"

    def __str__(self) -> str:
        return f"Benchmark {self.id}: {self.domain} ({self.complexity_level})"

    @property
    def quality_rating_percentage(self) -> int:
        """Get quality rating as percentage."""
        return int(float(self.quality_rating) * 100) if self.quality_rating else 0

    @property
    def coverage_percentage(self) -> int:
        """Get coverage completeness as percentage."""
        return int(float(self.coverage_completeness) * 100) if self.coverage_completeness else 0

    @property
    def expert_test_case_count(self) -> int:
        """Get the number of expert test cases in the benchmark."""
        if not self.expert_test_cases or not isinstance(self.expert_test_cases, list):
            return 0
        return len(self.expert_test_cases)

    @property
    def age_in_days(self) -> int:
        """Get the age of the benchmark in days."""
        if not self.benchmark_creation_date:
            return 0
        
        delta = datetime.utcnow() - self.benchmark_creation_date.replace(tzinfo=None)
        return delta.days

    @property
    def is_stale(self) -> bool:
        """Check if the benchmark might be stale (older than 1 year)."""
        return self.age_in_days > 365

    @property
    def needs_validation(self) -> bool:
        """Check if the benchmark needs validation (no validation in 6 months)."""
        if not self.last_validation_date:
            return True
        
        delta = datetime.utcnow() - self.last_validation_date.replace(tzinfo=None)
        return delta.days > 180

    @property
    def reviewer_level_weight(self) -> float:
        """Get weight multiplier based on reviewer experience level."""
        weights = {
            "expert": 1.0,
            "senior": 0.8,
            "junior": 0.6
        }
        return weights.get(self.reviewer_experience_level, 0.5)

    @property
    def weighted_quality_score(self) -> float:
        """Get quality score weighted by reviewer experience."""
        base_score = float(self.quality_rating) if self.quality_rating else 0.0
        return base_score * self.reviewer_level_weight

    def to_dict(self) -> Dict[str, Any]:
        """Convert the benchmark to a dictionary representation."""
        return {
            "id": self.id,
            "user_story_id": self.user_story_id,
            "benchmark_story_content": self.benchmark_story_content,
            "expert_test_cases": self.expert_test_cases,
            "expert_test_case_count": self.expert_test_case_count,
            "domain": self.domain,
            "complexity_level": self.complexity_level,
            "reviewer_id": self.reviewer_id,
            "reviewer_experience_level": self.reviewer_experience_level,
            "reviewer_level_weight": self.reviewer_level_weight,
            "quality_rating": float(self.quality_rating) if self.quality_rating else None,
            "quality_rating_percentage": self.quality_rating_percentage,
            "coverage_completeness": float(self.coverage_completeness) if self.coverage_completeness else None,
            "coverage_percentage": self.coverage_percentage,
            "weighted_quality_score": self.weighted_quality_score,
            "benchmark_creation_date": self.benchmark_creation_date.isoformat() if self.benchmark_creation_date else None,
            "last_validation_date": self.last_validation_date.isoformat() if self.last_validation_date else None,
            "is_active": self.is_active,
            "usage_count": self.usage_count,
            "age_in_days": self.age_in_days,
            "is_stale": self.is_stale,
            "needs_validation": self.needs_validation
        }

    def increment_usage(self) -> None:
        """Increment the usage count when this benchmark is used for comparison."""
        self.usage_count = (self.usage_count or 0) + 1

    def mark_as_validated(self, validation_date: Optional[datetime] = None) -> None:
        """Mark the benchmark as validated with current or specified date."""
        self.last_validation_date = validation_date or func.now()

    def deactivate(self) -> None:
        """Deactivate the benchmark (mark as no longer in use)."""
        self.is_active = False

    def reactivate(self) -> None:
        """Reactivate the benchmark for use."""
        self.is_active = True

    def get_test_cases_by_type(self, test_type: str) -> List[Dict[str, Any]]:
        """Get expert test cases filtered by type."""
        if not self.expert_test_cases or not isinstance(self.expert_test_cases, list):
            return []
        
        return [
            test_case for test_case in self.expert_test_cases 
            if isinstance(test_case, dict) and test_case.get("test_type") == test_type
        ]

    def get_test_case_statistics(self) -> Dict[str, Any]:
        """Get statistics about the expert test cases."""
        if not self.expert_test_cases or not isinstance(self.expert_test_cases, list):
            return {
                "total_count": 0,
                "by_type": {},
                "avg_steps": 0,
                "complexity_distribution": {}
            }
        
        # Count by type
        type_counts = {}
        total_steps = 0
        complexity_counts = {}
        
        for test_case in self.expert_test_cases:
            if not isinstance(test_case, dict):
                continue
            
            # Count by type
            test_type = test_case.get("test_type", "unknown")
            type_counts[test_type] = type_counts.get(test_type, 0) + 1
            
            # Count steps
            steps = test_case.get("steps", [])
            if isinstance(steps, list):
                total_steps += len(steps)
            
            # Count complexity
            complexity = test_case.get("complexity", "unknown")
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
        
        avg_steps = total_steps / len(self.expert_test_cases) if self.expert_test_cases else 0
        
        return {
            "total_count": len(self.expert_test_cases),
            "by_type": type_counts,
            "avg_steps": round(avg_steps, 1),
            "complexity_distribution": complexity_counts
        }

    def calculate_similarity_score(self, generated_test_cases: List[Dict[str, Any]]) -> float:
        """
        Calculate similarity score between generated test cases and this benchmark.
        
        Args:
            generated_test_cases: List of generated test cases to compare
            
        Returns:
            Similarity score between 0 and 1
        """
        if not self.expert_test_cases or not generated_test_cases:
            return 0.0
        
        # Simple similarity calculation based on test case count and types
        expert_types = set()
        for expert_case in self.expert_test_cases:
            if isinstance(expert_case, dict):
                expert_types.add(expert_case.get("test_type", "unknown"))
        
        generated_types = set()
        for generated_case in generated_test_cases:
            if isinstance(generated_case, dict):
                generated_types.add(generated_case.get("test_type", "unknown"))
        
        if not expert_types:
            return 0.0
        
        # Calculate type overlap
        type_overlap = len(expert_types.intersection(generated_types)) / len(expert_types)
        
        # Calculate count similarity (penalize significant differences)
        expert_count = len(self.expert_test_cases)
        generated_count = len(generated_test_cases)
        count_ratio = min(expert_count, generated_count) / max(expert_count, generated_count)
        
        # Combine scores
        similarity_score = (type_overlap * 0.7) + (count_ratio * 0.3)
        
        return min(1.0, max(0.0, similarity_score))

    @classmethod
    def create_benchmark(cls, user_story_id: int, story_content: Dict[str, Any], 
                        expert_test_cases: List[Dict[str, Any]], domain: str, 
                        complexity_level: str, reviewer_id: str, 
                        reviewer_experience: str, quality_rating: float, 
                        coverage_rating: float) -> "GroundTruthBenchmark":
        """
        Factory method to create a new benchmark.
        
        Args:
            user_story_id: ID of the associated user story
            story_content: Complete user story content
            expert_test_cases: List of expert-created test cases
            domain: Domain classification
            complexity_level: Complexity level
            reviewer_id: ID of the reviewing expert
            reviewer_experience: Experience level of reviewer
            quality_rating: Quality rating (0-1)
            coverage_rating: Coverage completeness rating (0-1)
            
        Returns:
            New GroundTruthBenchmark instance
        """
        return cls(
            user_story_id=user_story_id,
            benchmark_story_content=story_content,
            expert_test_cases=expert_test_cases,
            domain=domain,
            complexity_level=complexity_level,
            reviewer_id=reviewer_id,
            reviewer_experience_level=reviewer_experience,
            quality_rating=Decimal(str(quality_rating)),
            coverage_completeness=Decimal(str(coverage_rating)),
            benchmark_creation_date=func.now(),
            is_active=True,
            usage_count=0
        )
