"""
Generation Statistics model for tracking test case generation performance.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, Numeric, ForeignKey, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class GenerationStatistics(Base):
    """
    Generation Statistics model for tracking test case generation performance,
    timing, quality metrics, and resource usage.
    
    This model provides insights into system performance and helps
    optimize the generation process.
    """
    
    __tablename__ = "generation_statistics"
    __table_args__ = {"schema": "testgen"}

    # Primary fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_story_id = Column(
        Integer, 
        ForeignKey("testgen.user_stories.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Generation timing
    generation_start = Column(
        TIMESTAMP(timezone=True), 
        nullable=False,
        comment="When test case generation started"
    )
    generation_end = Column(
        TIMESTAMP(timezone=True),
        comment="When test case generation completed"
    )
    
    # Generation results
    test_cases_generated = Column(
        Integer, 
        default=0,
        comment="Total number of test cases generated"
    )
    test_cases_passed_validation = Column(
        Integer, 
        default=0,
        comment="Number of test cases that passed validation"
    )
    average_quality_score = Column(
        Numeric(3, 2),
        comment="Average quality score of generated test cases"
    )
    
    # Performance metrics
    processing_time_seconds = Column(
        Integer,
        comment="Total processing time in seconds"
    )
    tokens_used = Column(
        Integer,
        comment="Number of AI tokens consumed during generation"
    )
    
    # Generation configuration and errors
    generation_parameters = Column(
        JSONB,
        comment="Parameters and configuration used for generation"
    )
    errors = Column(
        JSONB,
        comment="Any errors encountered during generation"
    )
    
    # Relationships
    user_story = relationship("UserStory", back_populates="generation_statistics")

    def __repr__(self) -> str:
        return f"<GenerationStatistics(id={self.id}, user_story_id={self.user_story_id}, generated={self.test_cases_generated})>"

    def __str__(self) -> str:
        return f"Generation Stats {self.id}: {self.test_cases_generated} test cases"

    @property
    def is_completed(self) -> bool:
        """Check if generation is completed."""
        return self.generation_end is not None

    @property
    def validation_pass_rate(self) -> float:
        """Calculate validation pass rate as percentage."""
        if not self.test_cases_generated or self.test_cases_generated == 0:
            return 0.0
        
        return (self.test_cases_passed_validation / self.test_cases_generated) * 100

    @property
    def generation_duration_minutes(self) -> Optional[float]:
        """Get generation duration in minutes."""
        if not self.generation_start or not self.generation_end:
            return None
        
        delta = self.generation_end - self.generation_start
        return delta.total_seconds() / 60

    @property
    def tokens_per_test_case(self) -> Optional[float]:
        """Calculate average tokens used per test case."""
        if not self.tokens_used or not self.test_cases_generated or self.test_cases_generated == 0:
            return None
        
        return self.tokens_used / self.test_cases_generated

    @property
    def test_cases_per_minute(self) -> Optional[float]:
        """Calculate test cases generated per minute."""
        duration = self.generation_duration_minutes
        if not duration or duration == 0 or not self.test_cases_generated:
            return None
        
        return self.test_cases_generated / duration

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred during generation."""
        return (
            self.errors is not None and 
            isinstance(self.errors, list) and 
            len(self.errors) > 0
        )

    @property
    def error_count(self) -> int:
        """Get the number of errors that occurred."""
        if not self.errors or not isinstance(self.errors, list):
            return 0
        return len(self.errors)

    @property
    def performance_grade(self) -> str:
        """Get human-readable performance grade based on metrics."""
        # Base performance on validation pass rate and quality score
        pass_rate = self.validation_pass_rate
        quality_score = float(self.average_quality_score) if self.average_quality_score else 0.0
        
        # Calculate combined score
        combined_score = (pass_rate / 100 * 0.6) + (quality_score * 0.4)
        
        if combined_score >= 0.9:
            return "excellent"
        elif combined_score >= 0.8:
            return "good"
        elif combined_score >= 0.7:
            return "fair"
        elif combined_score >= 0.6:
            return "poor"
        else:
            return "very_poor"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the generation statistics to a dictionary representation."""
        return {
            "id": self.id,
            "user_story_id": self.user_story_id,
            "generation_start": self.generation_start.isoformat() if self.generation_start else None,
            "generation_end": self.generation_end.isoformat() if self.generation_end else None,
            "is_completed": self.is_completed,
            "test_cases_generated": self.test_cases_generated,
            "test_cases_passed_validation": self.test_cases_passed_validation,
            "validation_pass_rate": round(self.validation_pass_rate, 2),
            "average_quality_score": float(self.average_quality_score) if self.average_quality_score else None,
            "processing_time_seconds": self.processing_time_seconds,
            "generation_duration_minutes": round(self.generation_duration_minutes, 2) if self.generation_duration_minutes else None,
            "tokens_used": self.tokens_used,
            "tokens_per_test_case": round(self.tokens_per_test_case, 2) if self.tokens_per_test_case else None,
            "test_cases_per_minute": round(self.test_cases_per_minute, 2) if self.test_cases_per_minute else None,
            "generation_parameters": self.generation_parameters,
            "errors": self.errors,
            "has_errors": self.has_errors,
            "error_count": self.error_count,
            "performance_grade": self.performance_grade
        }

    def start_generation(self, parameters: Optional[Dict[str, Any]] = None) -> None:
        """Mark the start of generation process."""
        self.generation_start = func.now()
        if parameters:
            self.generation_parameters = parameters

    def complete_generation(self, test_cases_generated: int, test_cases_passed: int, 
                          average_quality: float, tokens_used: Optional[int] = None,
                          errors: Optional[List[Dict[str, Any]]] = None) -> None:
        """Mark the completion of generation process with results."""
        self.generation_end = func.now()
        self.test_cases_generated = test_cases_generated
        self.test_cases_passed_validation = test_cases_passed
        self.average_quality_score = Decimal(str(average_quality))
        
        if tokens_used is not None:
            self.tokens_used = tokens_used
        
        if errors:
            self.errors = errors
        
        # Calculate processing time
        if self.generation_start:
            delta = self.generation_end - self.generation_start
            self.processing_time_seconds = int(delta.total_seconds())

    def add_error(self, error_type: str, error_message: str, 
                 error_context: Optional[Dict[str, Any]] = None) -> None:
        """Add an error to the statistics."""
        if self.errors is None:
            self.errors = []
        
        error_entry = {
            "type": error_type,
            "message": error_message,
            "context": error_context,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.errors.append(error_entry)

    def get_errors_by_type(self, error_type: str) -> List[Dict[str, Any]]:
        """Get errors filtered by type."""
        if not self.errors or not isinstance(self.errors, list):
            return []
        
        return [
            error for error in self.errors 
            if isinstance(error, dict) and error.get("type") == error_type
        ]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of performance metrics."""
        return {
            "generation_efficiency": {
                "test_cases_generated": self.test_cases_generated,
                "validation_pass_rate": self.validation_pass_rate,
                "average_quality_score": float(self.average_quality_score) if self.average_quality_score else None,
                "performance_grade": self.performance_grade
            },
            "timing_metrics": {
                "processing_time_seconds": self.processing_time_seconds,
                "generation_duration_minutes": self.generation_duration_minutes,
                "test_cases_per_minute": self.test_cases_per_minute
            },
            "resource_usage": {
                "tokens_used": self.tokens_used,
                "tokens_per_test_case": self.tokens_per_test_case
            },
            "error_summary": {
                "has_errors": self.has_errors,
                "error_count": self.error_count
            }
        }

    @classmethod
    def create_for_user_story(cls, user_story_id: int, 
                            parameters: Optional[Dict[str, Any]] = None) -> "GenerationStatistics":
        """
        Factory method to create generation statistics for a user story.
        
        Args:
            user_story_id: ID of the user story being processed
            parameters: Optional generation parameters
            
        Returns:
            New GenerationStatistics instance with generation started
        """
        stats = cls(
            user_story_id=user_story_id,
            generation_start=func.now(),
            test_cases_generated=0,
            test_cases_passed_validation=0
        )
        
        if parameters:
            stats.generation_parameters = parameters
        
        return stats
