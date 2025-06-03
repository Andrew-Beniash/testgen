"""
SQLAlchemy Models for Test Generation Agent v2.0
Enhanced models with quality assurance, learning capabilities, and comprehensive relationships.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
import json

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Numeric, 
    ForeignKey, CheckConstraint, Index, JSON, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates, Session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import TypeDecorator, VARCHAR
from pydantic import BaseModel as PydanticBaseModel, Field, field_validator
import uuid

Base = declarative_base()

# Enums for type safety
class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUEUED_FOR_REVIEW = "queued_for_review"

class TestClassification(str, Enum):
    MANUAL = "manual"
    API_AUTOMATION = "api_automation"
    UI_AUTOMATION = "ui_automation"
    PERFORMANCE = "performance"
    SECURITY = "security"
    INTEGRATION = "integration"

class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class QualityRating(int, Enum):
    POOR = 1
    FAIR = 2
    GOOD = 3
    VERY_GOOD = 4
    EXCELLENT = 5

class ExecutionDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    IMPOSSIBLE = "impossible"

# Custom type for handling choice fields
class ChoiceType(TypeDecorator):
    impl = VARCHAR
    
    def __init__(self, choices, **kw):
        self.choices = dict(choices)
        super(ChoiceType, self).__init__(**kw)
    
    def process_bind_param(self, value, dialect):
        return [k for k, v in self.choices.items() if v == value][0]
    
    def process_result_value(self, value, dialect):
        return self.choices[value]

# Soft delete mixin
class SoftDeleteMixin:
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    def soft_delete(self):
        """Mark record as deleted without actually removing it."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
    
    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
    
    @classmethod
    def active_only(cls, query):
        """Filter query to only include non-deleted records."""
        return query.filter(cls.is_deleted == False)

# Audit mixin for tracking changes
class AuditMixin:
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), 
                       onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)

# Base model with common functionality
class BaseModel(Base, AuditMixin, SoftDeleteMixin):
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    def to_dict(self, exclude_deleted=True):
        """Convert model to dictionary."""
        if exclude_deleted and hasattr(self, 'is_deleted') and self.is_deleted:
            return None
            
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            elif isinstance(value, (dict, list)):
                result[column.name] = value
            else:
                result[column.name] = value
        return result
    
    @classmethod
    def from_dict(cls, data: dict, session: Session = None):
        """Create model instance from dictionary."""
        # Remove audit fields that should be set automatically
        excluded_fields = {'id', 'created_at', 'updated_at', 'deleted_at'}
        filtered_data = {k: v for k, v in data.items() if k not in excluded_fields}
        return cls(**filtered_data)

# Enhanced User Story Model
class UserStory(BaseModel):
    __tablename__ = 'user_stories'
    
    # Core fields
    azure_devops_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    acceptance_criteria = Column(Text, nullable=False)
    
    # Original content before normalization
    original_content = Column(JSONB, nullable=True)
    
    # Enhanced metadata
    normalization_metadata = Column(JSONB, nullable=True)
    complexity_analysis = Column(JSONB, nullable=True)
    quality_prediction = Column(JSONB, nullable=True)
    domain_classification = Column(String(50), nullable=True, index=True)
    
    # Processing status
    processing_status = Column(
        ChoiceType([(status.value, status) for status in ProcessingStatus]),
        default=ProcessingStatus.PENDING,
        nullable=False,
        index=True
    )
    processing_metadata = Column(JSONB, nullable=True)
    
    # Quality tracking
    generation_quality_score = Column(Numeric(3, 2), nullable=True)
    
    # Vector embedding for similarity search
    embedding = Column(JSONB, nullable=True)
    combined_embedding = Column(JSONB, nullable=True)
    
    # Relationships
    test_cases = relationship("TestCase", back_populates="user_story", lazy="dynamic")
    quality_metrics = relationship("QualityMetrics", back_populates="user_story", lazy="dynamic")
    benchmark_entries = relationship("GroundTruthBenchmark", back_populates="user_story", lazy="dynamic")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('length(title) >= 10 AND length(title) <= 500', name='title_length_check'),
        CheckConstraint('length(description) >= 50 AND length(description) <= 5000', name='description_length_check'),
        CheckConstraint('length(acceptance_criteria) >= 20 AND length(acceptance_criteria) <= 3000', name='acceptance_criteria_length_check'),
        CheckConstraint('generation_quality_score >= 0 AND generation_quality_score <= 1', name='quality_score_range_check'),
        Index('idx_user_stories_domain_status', 'domain_classification', 'processing_status'),
        Index('idx_user_stories_quality_score', 'generation_quality_score'),
    )
    
    @validates('title', 'description', 'acceptance_criteria')
    def validate_content_length(self, key, value):
        """Validate content length constraints."""
        if key == 'title' and value:
            if len(value) < 10 or len(value) > 500:
                raise ValueError(f"Title must be between 10 and 500 characters, got {len(value)}")
        elif key == 'description' and value:
            if len(value) < 50 or len(value) > 5000:
                raise ValueError(f"Description must be between 50 and 5000 characters, got {len(value)}")
        elif key == 'acceptance_criteria' and value:
            if len(value) < 20 or len(value) > 3000:
                raise ValueError(f"Acceptance criteria must be between 20 and 3000 characters, got {len(value)}")
        return value
    
    @hybrid_property
    def complexity_score(self):
        """Get overall complexity score from analysis."""
        if self.complexity_analysis:
            return self.complexity_analysis.get('overall_score', 0.0)
        return 0.0
    
    def get_active_test_cases(self):
        """Get non-deleted test cases."""
        return self.test_cases.filter(TestCase.is_deleted == False)
    
    def get_average_test_case_quality(self):
        """Calculate average quality of associated test cases."""
        active_cases = self.get_active_test_cases().all()
        if not active_cases:
            return None
        
        total_quality = sum(tc.get_latest_quality_score() or 0 for tc in active_cases)
        return total_quality / len(active_cases)
    
    def mark_processing_complete(self, session: Session):
        """Mark story processing as complete and update metadata."""
        self.processing_status = ProcessingStatus.COMPLETED
        if not self.processing_metadata:
            self.processing_metadata = {}
        self.processing_metadata['completed_at'] = datetime.now(timezone.utc).isoformat()
        session.commit()

# Enhanced Test Case Model
class TestCase(BaseModel):
    __tablename__ = 'test_cases'
    
    # Core fields
    user_story_id = Column(Integer, ForeignKey('user_stories.id'), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    
    # Test steps stored as JSONB
    steps = Column(JSONB, nullable=False)
    
    # Enhanced classification
    classification = Column(
        ChoiceType([(cls.value, cls) for cls in TestClassification]),
        nullable=False,
        index=True
    )
    classification_confidence = Column(Numeric(3, 2), nullable=False, default=0.0)
    classification_reasoning = Column(Text, nullable=True)
    
    # Test metadata
    test_type = Column(String(50), nullable=True, index=True)  # positive, negative, edge
    estimated_duration = Column(Integer, nullable=True)  # minutes
    priority = Column(String(20), nullable=True, default='medium')
    tags = Column(JSONB, nullable=True)
    
    # Quality and validation
    validation_status = Column(JSONB, nullable=True)
    confidence_score = Column(Numeric(3, 2), nullable=False, default=0.0)
    quality_issues = Column(JSONB, nullable=True)
    
    # Generation metadata
    generation_metadata = Column(JSONB, nullable=True)
    benchmark_references = Column(JSONB, nullable=True)
    persona_context = Column(JSONB, nullable=True)
    
    # Vector embedding for similarity
    embedding = Column(JSONB, nullable=True)
    
    # Relationships
    user_story = relationship("UserStory", back_populates="test_cases")
    quality_metrics = relationship("QualityMetrics", back_populates="test_case", lazy="dynamic")
    qa_annotations = relationship("QAAnnotation", back_populates="test_case", lazy="dynamic")
    execution_feedback = relationship("ExecutionFeedback", back_populates="test_case", uselist=False)
    learning_contributions = relationship("LearningContribution", back_populates="test_case", lazy="dynamic")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('length(title) >= 10 AND length(title) <= 500', name='tc_title_length_check'),
        CheckConstraint('length(description) >= 20 AND length(description) <= 2000', name='tc_description_length_check'),
        CheckConstraint('classification_confidence >= 0 AND classification_confidence <= 1', name='tc_classification_confidence_check'),
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='tc_confidence_score_check'),
        CheckConstraint('estimated_duration > 0', name='tc_duration_positive_check'),
        Index('idx_test_cases_classification_confidence', 'classification', 'classification_confidence'),
        Index('idx_test_cases_user_story_type', 'user_story_id', 'test_type'),
    )
    
    @validates('steps')
    def validate_steps(self, key, value):
        """Validate test steps structure."""
        if not isinstance(value, list):
            raise ValueError("Steps must be a list")
        
        if len(value) < 2:
            raise ValueError("Test case must have at least 2 steps")
        
        if len(value) > 20:
            raise ValueError("Test case cannot have more than 20 steps")
        
        for i, step in enumerate(value):
            if not isinstance(step, dict):
                raise ValueError(f"Step {i+1} must be a dictionary")
            
            required_fields = {'step_number', 'action', 'expected_result'}
            if not all(field in step for field in required_fields):
                raise ValueError(f"Step {i+1} missing required fields: {required_fields}")
        
        return value
    
    def get_latest_quality_score(self):
        """Get the most recent quality score."""
        latest_metric = (self.quality_metrics
                        .filter(QualityMetrics.is_deleted == False)
                        .order_by(QualityMetrics.calculated_at.desc())
                        .first())
        return latest_metric.overall_score if latest_metric else None
    
    def get_step_count(self):
        """Get number of test steps."""
        return len(self.steps) if self.steps else 0
    
    def add_quality_issue(self, issue_type: str, description: str, severity: str = "medium"):
        """Add a quality issue to the test case."""
        if not self.quality_issues:
            self.quality_issues = []
        
        issue = {
            'type': issue_type,
            'description': description,
            'severity': severity,
            'identified_at': datetime.now(timezone.utc).isoformat()
        }
        self.quality_issues.append(issue)
    
    def clear_quality_issues(self):
        """Clear all quality issues."""
        self.quality_issues = []
    
    def is_automation_ready(self):
        """Check if test case is ready for automation."""
        return (self.classification in [TestClassification.API_AUTOMATION, TestClassification.UI_AUTOMATION] 
                and self.classification_confidence >= 0.7
                and self.get_latest_quality_score() and self.get_latest_quality_score() >= 0.75)

# Quality Metrics Model
class QualityMetrics(BaseModel):
    __tablename__ = 'quality_metrics'
    
    # Foreign keys
    test_case_id = Column(Integer, ForeignKey('test_cases.id'), nullable=True, index=True)
    user_story_id = Column(Integer, ForeignKey('user_stories.id'), nullable=True, index=True)
    
    # Quality dimensions (0-1 scale)
    overall_score = Column(Numeric(3, 2), nullable=False)
    clarity_score = Column(Numeric(3, 2), nullable=False)
    completeness_score = Column(Numeric(3, 2), nullable=False)
    executability_score = Column(Numeric(3, 2), nullable=False)
    traceability_score = Column(Numeric(3, 2), nullable=False)
    realism_score = Column(Numeric(3, 2), nullable=False)
    coverage_score = Column(Numeric(3, 2), nullable=False)
    
    # Quality metadata
    confidence_level = Column(
        ChoiceType([(level.value, level) for level in ConfidenceLevel]),
        nullable=False,
        default=ConfidenceLevel.MEDIUM,
        index=True
    )
    quality_issues_count = Column(Integer, default=0, nullable=False)
    validation_passed = Column(Boolean, default=False, nullable=False)
    benchmark_percentile = Column(Numeric(5, 2), nullable=True)
    
    # Calculation metadata
    calculated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    calculation_version = Column(String(20), nullable=False, default="1.0")
    calculation_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    test_case = relationship("TestCase", back_populates="quality_metrics")
    user_story = relationship("UserStory", back_populates="quality_metrics")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('overall_score >= 0 AND overall_score <= 1', name='qm_overall_score_range'),
        CheckConstraint('clarity_score >= 0 AND clarity_score <= 1', name='qm_clarity_score_range'),
        CheckConstraint('completeness_score >= 0 AND completeness_score <= 1', name='qm_completeness_score_range'),
        CheckConstraint('executability_score >= 0 AND executability_score <= 1', name='qm_executability_score_range'),
        CheckConstraint('traceability_score >= 0 AND traceability_score <= 1', name='qm_traceability_score_range'),
        CheckConstraint('realism_score >= 0 AND realism_score <= 1', name='qm_realism_score_range'),
        CheckConstraint('coverage_score >= 0 AND coverage_score <= 1', name='qm_coverage_score_range'),
        CheckConstraint('benchmark_percentile >= 0 AND benchmark_percentile <= 100', name='qm_percentile_range'),
        CheckConstraint('quality_issues_count >= 0', name='qm_issues_count_positive'),
        Index('idx_quality_metrics_overall_score', 'overall_score', 'calculated_at'),
        Index('idx_quality_metrics_test_case_score', 'test_case_id', 'overall_score'),
    )
    
    @validates('overall_score', 'clarity_score', 'completeness_score', 'executability_score', 
              'traceability_score', 'realism_score', 'coverage_score')
    def validate_score_range(self, key, value):
        """Validate that all scores are in the 0-1 range."""
        if value is not None and (value < 0 or value > 1):
            raise ValueError(f"{key} must be between 0 and 1, got {value}")
        return value
    
    def calculate_weighted_score(self, weights: Dict[str, float] = None):
        """Calculate weighted quality score with custom weights."""
        if weights is None:
            # Default weights from specification
            weights = {
                'clarity': 0.25,
                'completeness': 0.25,
                'executability': 0.20,
                'traceability': 0.15,
                'realism': 0.10,
                'coverage': 0.05
            }
        
        weighted_score = (
            self.clarity_score * weights.get('clarity', 0.25) +
            self.completeness_score * weights.get('completeness', 0.25) +
            self.executability_score * weights.get('executability', 0.20) +
            self.traceability_score * weights.get('traceability', 0.15) +
            self.realism_score * weights.get('realism', 0.10) +
            self.coverage_score * weights.get('coverage', 0.05)
        )
        
        return round(weighted_score, 2)
    
    def passes_quality_threshold(self, threshold: float = 0.75):
        """Check if quality meets the specified threshold."""
        return self.overall_score >= threshold and self.validation_passed
    
    def get_quality_grade(self):
        """Get letter grade based on overall score."""
        if self.overall_score >= 0.90:
            return 'A'
        elif self.overall_score >= 0.80:
            return 'B'
        elif self.overall_score >= 0.70:
            return 'C'
        elif self.overall_score >= 0.60:
            return 'D'
        else:
            return 'F'

# QA Annotation Model for Learning
class QAAnnotation(BaseModel):
    __tablename__ = 'qa_annotations'
    
    # Foreign keys
    test_case_id = Column(Integer, ForeignKey('test_cases.id'), nullable=False, index=True)
    annotator_id = Column(String(100), nullable=False, index=True)
    
    # Quality assessment
    overall_quality_rating = Column(
        ChoiceType([(rating.value, rating) for rating in QualityRating]),
        nullable=False
    )
    quality_issues = Column(JSONB, nullable=True)
    positive_aspects = Column(JSONB, nullable=True)
    
    # Specific feedback
    clarity_feedback = Column(Text, nullable=True)
    completeness_feedback = Column(Text, nullable=True)
    executability_feedback = Column(Text, nullable=True)
    improvement_suggestions = Column(JSONB, nullable=True)
    
    # Classification feedback
    suggested_classification = Column(
        ChoiceType([(cls.value, cls) for cls in TestClassification]),
        nullable=True
    )
    classification_reasoning = Column(Text, nullable=True)
    
    # Execution feedback
    execution_difficulty = Column(
        ChoiceType([(diff.value, diff) for diff in ExecutionDifficulty]),
        nullable=True
    )
    execution_time_actual = Column(Integer, nullable=True)  # minutes
    execution_issues = Column(JSONB, nullable=True)
    
    # Processing status
    annotation_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    processing_timestamp = Column(DateTime(timezone=True), nullable=True)
    annotator_notes = Column(Text, nullable=True)
    
    # Relationships
    test_case = relationship("TestCase", back_populates="qa_annotations")
    learning_contributions = relationship("LearningContribution", back_populates="annotation", lazy="dynamic")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('execution_time_actual > 0', name='qa_execution_time_positive'),
        Index('idx_qa_annotations_rating_timestamp', 'overall_quality_rating', 'annotation_timestamp'),
        Index('idx_qa_annotations_processed', 'is_processed', 'processing_timestamp'),
    )
    
    def mark_processed(self, session: Session):
        """Mark annotation as processed."""
        self.is_processed = True
        self.processing_timestamp = datetime.now(timezone.utc)
        session.commit()
    
    def get_quality_issues_summary(self):
        """Get summary of quality issues."""
        if not self.quality_issues:
            return {}
        
        issue_counts = {}
        for issue in self.quality_issues:
            issue_type = issue.get('type', 'unknown')
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        return issue_counts

# Learning Contribution Model
class LearningContribution(BaseModel):
    __tablename__ = 'learning_contributions'
    
    # Foreign keys
    test_case_id = Column(Integer, ForeignKey('test_cases.id'), nullable=False, index=True)
    annotation_id = Column(Integer, ForeignKey('qa_annotations.id'), nullable=True, index=True)
    
    # Contribution metadata
    contribution_type = Column(String(50), nullable=False, index=True)
    pattern_identified = Column(JSONB, nullable=True)
    improvement_applied = Column(Text, nullable=True)
    quality_impact = Column(Numeric(3, 2), nullable=True)
    
    # Model updates
    prompt_updates = Column(JSONB, nullable=True)
    model_training_data = Column(JSONB, nullable=True)
    validation_rule_updates = Column(JSONB, nullable=True)
    
    # Timestamps
    contribution_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    applied_timestamp = Column(DateTime(timezone=True), nullable=True)
    effectiveness_score = Column(Numeric(3, 2), nullable=True)
    
    # Relationships
    test_case = relationship("TestCase", back_populates="learning_contributions")
    annotation = relationship("QAAnnotation", back_populates="learning_contributions")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('quality_impact >= -1 AND quality_impact <= 1', name='lc_quality_impact_range'),
        CheckConstraint('effectiveness_score >= 0 AND effectiveness_score <= 1', name='lc_effectiveness_range'),
        Index('idx_learning_contributions_type_impact', 'contribution_type', 'quality_impact'),
    )

# Execution Feedback Model
class ExecutionFeedback(BaseModel):
    __tablename__ = 'execution_feedback'
    
    # Foreign key
    test_case_id = Column(Integer, ForeignKey('test_cases.id'), nullable=False, unique=True, index=True)
    
    # Execution results
    execution_status = Column(String(20), nullable=False)  # passed, failed, blocked, skipped
    execution_time_actual = Column(Integer, nullable=True)  # minutes
    execution_difficulty_actual = Column(
        ChoiceType([(diff.value, diff) for diff in ExecutionDifficulty]),
        nullable=True
    )
    
    # Issues and feedback
    execution_issues = Column(JSONB, nullable=True)
    test_environment = Column(String(100), nullable=True)
    executor_notes = Column(Text, nullable=True)
    defects_found = Column(JSONB, nullable=True)
    
    # Metadata
    executed_by = Column(String(100), nullable=False)
    execution_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    test_case = relationship("TestCase", back_populates="execution_feedback")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('execution_time_actual > 0', name='ef_execution_time_positive'),
        Index('idx_execution_feedback_status_date', 'execution_status', 'execution_date'),
    )

# Ground Truth Benchmark Model
class GroundTruthBenchmark(BaseModel):
    __tablename__ = 'ground_truth_benchmark'
    
    # Foreign key
    user_story_id = Column(Integer, ForeignKey('user_stories.id'), nullable=False, index=True)
    
    # Benchmark content
    benchmark_story_content = Column(JSONB, nullable=False)
    expert_test_cases = Column(JSONB, nullable=False)
    
    # Classification metadata
    domain = Column(String(50), nullable=False, index=True)
    complexity_level = Column(String(20), nullable=False, index=True)
    
    # Quality assessment
    reviewer_id = Column(String(100), nullable=False)
    reviewer_experience_level = Column(String(20), nullable=False)
    quality_rating = Column(Numeric(3, 2), nullable=False)
    coverage_completeness = Column(Numeric(3, 2), nullable=False)
    
    # Lifecycle management
    benchmark_creation_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_validation_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    user_story = relationship("UserStory", back_populates="benchmark_entries")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('quality_rating >= 0 AND quality_rating <= 1', name='gtb_quality_rating_range'),
        CheckConstraint('coverage_completeness >= 0 AND coverage_completeness <= 1', name='gtb_coverage_range'),
        CheckConstraint('usage_count >= 0', name='gtb_usage_count_positive'),
        Index('idx_benchmark_domain_complexity', 'domain', 'complexity_level', 'quality_rating'),
        Index('idx_benchmark_active_usage', 'is_active', 'usage_count'),
    )
    
    def increment_usage(self, session: Session):
        """Increment usage count when benchmark is used."""
        self.usage_count += 1
        session.commit()
    
    def validate_benchmark(self, session: Session):
        """Update last validation date."""
        self.last_validation_date = datetime.now(timezone.utc)
        session.commit()

# Database utility functions
class DatabaseManager:
    """Utility class for database operations."""
    
    @staticmethod
    def create_user_story_with_validation(session: Session, story_data: dict) -> UserStory:
        """Create a new user story with validation."""
        try:
            user_story = UserStory.from_dict(story_data, session)
            session.add(user_story)
            session.commit()
            session.refresh(user_story)
            return user_story
        except Exception as e:
            session.rollback()
            raise ValueError(f"Failed to create user story: {str(e)}")
    
    @staticmethod
    def create_test_case_with_quality(session: Session, test_case_data: dict, 
                                    quality_metrics: dict) -> TestCase:
        """Create test case with associated quality metrics."""
        try:
            # Create test case
            test_case = TestCase.from_dict(test_case_data, session)
            session.add(test_case)
            session.flush()  # Get ID without committing
            
            # Create quality metrics
            quality_data = {
                'test_case_id': test_case.id,
                **quality_metrics
            }
            quality_metric = QualityMetrics.from_dict(quality_data, session)
            session.add(quality_metric)
            
            session.commit()
            session.refresh(test_case)
            return test_case
        except Exception as e:
            session.rollback()
            raise ValueError(f"Failed to create test case with quality: {str(e)}")
    
    @staticmethod
    def get_quality_statistics(session: Session, days: int = 30) -> dict:
        """Get quality statistics for the specified period."""
        from sqlalchemy import func
        from datetime import timedelta
        
        since_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Query quality metrics
        quality_stats = session.query(
            func.count(QualityMetrics.id).label('total_metrics'),
            func.avg(QualityMetrics.overall_score).label('avg_quality'),
            func.min(QualityMetrics.overall_score).label('min_quality'),
            func.max(QualityMetrics.overall_score).label('max_quality'),
            func.stddev(QualityMetrics.overall_score).label('std_quality')
        ).filter(
            QualityMetrics.calculated_at >= since_date,
            QualityMetrics.is_deleted == False
        ).first()
        
        # Query test case classification distribution
        classification_stats = session.query(
            TestCase.classification,
            func.count(TestCase.id).label('count'),
            func.avg(QualityMetrics.overall_score).label('avg_quality')
        ).join(QualityMetrics).filter(
            TestCase.created_at >= since_date,
            TestCase.is_deleted == False,
            QualityMetrics.is_deleted == False
        ).group_by(TestCase.classification).all()
        
        return {
            'period_days': days,
            'total_metrics': quality_stats.total_metrics or 0,
            'average_quality': float(quality_stats.avg_quality or 0),
            'min_quality': float(quality_stats.min_quality or 0),
            'max_quality': float(quality_stats.max_quality or 0),
            'quality_std_dev': float(quality_stats.std_quality or 0),
            'classification_distribution': [
                {
                    'classification': stat.classification,
                    'count': stat.count,
                    'avg_quality': float(stat.avg_quality or 0)
                }
                for stat in classification_stats
            ]
        }
    
    @staticmethod
    def soft_delete_user_story_cascade(session: Session, user_story_id: int):
        """Soft delete user story and all associated records."""
        try:
            # Get user story
            user_story = session.query(UserStory).filter(
                UserStory.id == user_story_id,
                UserStory.is_deleted == False
            ).first()
            
            if not user_story:
                raise ValueError(f"User story {user_story_id} not found or already deleted")
            
            # Soft delete all associated test cases
            test_cases = session.query(TestCase).filter(
                TestCase.user_story_id == user_story_id,
                TestCase.is_deleted == False
            ).all()
            
            for test_case in test_cases:
                test_case.soft_delete()
                
                # Soft delete associated quality metrics
                quality_metrics = session.query(QualityMetrics).filter(
                    QualityMetrics.test_case_id == test_case.id,
                    QualityMetrics.is_deleted == False
                ).all()
                
                for qm in quality_metrics:
                    qm.soft_delete()
            
            # Soft delete user story quality metrics
            story_quality_metrics = session.query(QualityMetrics).filter(
                QualityMetrics.user_story_id == user_story_id,
                QualityMetrics.is_deleted == False
            ).all()
            
            for qm in story_quality_metrics:
                qm.soft_delete()
            
            # Finally soft delete the user story
            user_story.soft_delete()
            
            session.commit()
            return True
            
        except Exception as e:
            session.rollback()
            raise ValueError(f"Failed to soft delete user story: {str(e)}")

# Pydantic models for serialization/deserialization
class UserStorySchema(PydanticBaseModel):
    """Pydantic schema for UserStory serialization."""
    id: Optional[int] = None
    azure_devops_id: str
    title: str = Field(..., min_length=10, max_length=500)
    description: str = Field(..., min_length=50, max_length=5000)
    acceptance_criteria: str = Field(..., min_length=20, max_length=3000)
    domain_classification: Optional[str] = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    generation_quality_score: Optional[float] = Field(None, ge=0, le=1)
    original_content: Optional[Dict[str, Any]] = None
    normalization_metadata: Optional[Dict[str, Any]] = None
    complexity_analysis: Optional[Dict[str, Any]] = None
    quality_prediction: Optional[Dict[str, Any]] = None
    processing_metadata: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None
    combined_embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_deleted: bool = False
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        """Validate title field."""
        if len(v) < 10 or len(v) > 500:
            raise ValueError('Title must be between 10 and 500 characters')
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        """Validate description field."""
        if len(v) < 50 or len(v) > 5000:
            raise ValueError('Description must be between 50 and 5000 characters')
        return v
    
    @field_validator('acceptance_criteria')
    @classmethod
    def validate_acceptance_criteria(cls, v):
        """Validate acceptance criteria field."""
        if len(v) < 20 or len(v) > 3000:
            raise ValueError('Acceptance criteria must be between 20 and 3000 characters')
        return v

class TestStepSchema(PydanticBaseModel):
    """Schema for individual test step."""
    step_number: int = Field(..., ge=1)
    action: str = Field(..., min_length=5, max_length=1000)
    expected_result: str = Field(..., min_length=5, max_length=1000)
    test_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

class TestCaseSchema(PydanticBaseModel):
    """Pydantic schema for TestCase serialization."""
    id: Optional[int] = None
    user_story_id: int
    title: str = Field(..., min_length=10, max_length=500)
    description: str = Field(..., min_length=20, max_length=2000)
    steps: List[TestStepSchema] = Field(..., min_items=2, max_items=20)
    classification: TestClassification
    classification_confidence: float = Field(..., ge=0, le=1)
    classification_reasoning: Optional[str] = None
    test_type: Optional[str] = None
    estimated_duration: Optional[int] = Field(None, gt=0)
    priority: str = "medium"
    tags: Optional[List[str]] = None
    validation_status: Optional[Dict[str, Any]] = None
    confidence_score: float = Field(0.0, ge=0, le=1)
    quality_issues: Optional[List[Dict[str, Any]]] = None
    generation_metadata: Optional[Dict[str, Any]] = None
    benchmark_references: Optional[List[Dict[str, Any]]] = None
    persona_context: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_deleted: bool = False
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @field_validator('steps')
    @classmethod
    def validate_steps_structure(cls, v):
        """Validate test steps structure."""
        if len(v) < 2:
            raise ValueError('Test case must have at least 2 steps')
        if len(v) > 20:
            raise ValueError('Test case cannot have more than 20 steps')
        
        step_numbers = [step.step_number for step in v]
        expected_numbers = list(range(1, len(v) + 1))
        if step_numbers != expected_numbers:
            raise ValueError('Step numbers must be sequential starting from 1')
        
        return v

class QualityMetricsSchema(PydanticBaseModel):
    """Pydantic schema for QualityMetrics serialization."""
    id: Optional[int] = None
    test_case_id: Optional[int] = None
    user_story_id: Optional[int] = None
    overall_score: float = Field(..., ge=0, le=1)
    clarity_score: float = Field(..., ge=0, le=1)
    completeness_score: float = Field(..., ge=0, le=1)
    executability_score: float = Field(..., ge=0, le=1)
    traceability_score: float = Field(..., ge=0, le=1)
    realism_score: float = Field(..., ge=0, le=1)
    coverage_score: float = Field(..., ge=0, le=1)
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    quality_issues_count: int = Field(0, ge=0)
    validation_passed: bool = False
    benchmark_percentile: Optional[float] = Field(None, ge=0, le=100)
    calculated_at: Optional[datetime] = None
    calculation_version: str = "1.0"
    calculation_metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @field_validator('overall_score', 'clarity_score', 'completeness_score', 
                     'executability_score', 'traceability_score', 'realism_score', 
                     'coverage_score')
    @classmethod
    def validate_score_range(cls, v):
        """Validate score is in 0-1 range."""
        if v < 0 or v > 1:
            raise ValueError('Score must be between 0 and 1')
        return v

class QAAnnotationSchema(PydanticBaseModel):
    """Pydantic schema for QAAnnotation serialization."""
    id: Optional[int] = None
    test_case_id: int
    annotator_id: str
    overall_quality_rating: QualityRating
    quality_issues: Optional[List[Dict[str, Any]]] = None
    positive_aspects: Optional[List[str]] = None
    clarity_feedback: Optional[str] = None
    completeness_feedback: Optional[str] = None
    executability_feedback: Optional[str] = None
    improvement_suggestions: Optional[List[Dict[str, Any]]] = None
    suggested_classification: Optional[TestClassification] = None
    classification_reasoning: Optional[str] = None
    execution_difficulty: Optional[ExecutionDifficulty] = None
    execution_time_actual: Optional[int] = Field(None, gt=0)
    execution_issues: Optional[List[str]] = None
    annotation_timestamp: Optional[datetime] = None
    is_processed: bool = False
    processing_timestamp: Optional[datetime] = None
    annotator_notes: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

# Model conversion utilities
class ModelConverter:
    """Utility class for converting between SQLAlchemy models and Pydantic schemas."""
    
    @staticmethod
    def user_story_to_schema(user_story: UserStory) -> UserStorySchema:
        """Convert UserStory model to schema."""
        return UserStorySchema.from_orm(user_story)
    
    @staticmethod
    def schema_to_user_story(schema: UserStorySchema, session: Session) -> UserStory:
        """Convert UserStory schema to model."""
        data = schema.dict(exclude={'id', 'created_at', 'updated_at'})
        return UserStory(**data)
    
    @staticmethod
    def test_case_to_schema(test_case: TestCase) -> TestCaseSchema:
        """Convert TestCase model to schema."""
        # Convert steps from JSONB to TestStepSchema list
        steps_data = test_case.steps or []
        steps = [TestStepSchema(**step) for step in steps_data]
        
        data = test_case.to_dict()
        data['steps'] = steps
        return TestCaseSchema(**data)
    
    @staticmethod
    def schema_to_test_case(schema: TestCaseSchema, session: Session) -> TestCase:
        """Convert TestCase schema to model."""
        data = schema.dict(exclude={'id', 'created_at', 'updated_at'})
        # Convert steps to JSONB format
        data['steps'] = [step.dict() for step in schema.steps]
        return TestCase(**data)
    
    @staticmethod
    def quality_metrics_to_schema(quality_metrics: QualityMetrics) -> QualityMetricsSchema:
        """Convert QualityMetrics model to schema."""
        return QualityMetricsSchema.from_orm(quality_metrics)
    
    @staticmethod
    def schema_to_quality_metrics(schema: QualityMetricsSchema, session: Session) -> QualityMetrics:
        """Convert QualityMetrics schema to model."""
        data = schema.dict(exclude={'id', 'calculated_at'})
        return QualityMetrics(**data)

# Query builders for common operations
class QueryBuilder:
    """Helper class for building common queries."""
    
    @staticmethod
    def get_high_quality_test_cases(session: Session, threshold: float = 0.75):
        """Get test cases with quality above threshold."""
        return session.query(TestCase).join(QualityMetrics).filter(
            TestCase.is_deleted == False,
            QualityMetrics.is_deleted == False,
            QualityMetrics.overall_score >= threshold,
            QualityMetrics.validation_passed == True
        )
    
    @staticmethod
    def get_test_cases_needing_review(session: Session, threshold: float = 0.75):
        """Get test cases that need human review due to low quality."""
        return session.query(TestCase).join(QualityMetrics).filter(
            TestCase.is_deleted == False,
            QualityMetrics.is_deleted == False,
            QualityMetrics.overall_score < threshold
        )
    
    @staticmethod
    def get_user_stories_by_domain(session: Session, domain: str):
        """Get user stories filtered by domain."""
        return session.query(UserStory).filter(
            UserStory.is_deleted == False,
            UserStory.domain_classification == domain
        )
    
    @staticmethod
    def get_automation_ready_test_cases(session: Session):
        """Get test cases ready for automation."""
        automation_classifications = [
            TestClassification.API_AUTOMATION,
            TestClassification.UI_AUTOMATION
        ]
        
        return session.query(TestCase).join(QualityMetrics).filter(
            TestCase.is_deleted == False,
            TestCase.classification.in_(automation_classifications),
            TestCase.classification_confidence >= 0.7,
            QualityMetrics.is_deleted == False,
            QualityMetrics.overall_score >= 0.75,
            QualityMetrics.validation_passed == True
        )
    
    @staticmethod
    def get_quality_trends(session: Session, days: int = 30):
        """Get quality trends over time."""
        from sqlalchemy import func
        from datetime import timedelta
        
        since_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        return session.query(
            func.date(QualityMetrics.calculated_at).label('date'),
            func.avg(QualityMetrics.overall_score).label('avg_quality'),
            func.count(QualityMetrics.id).label('count')
        ).filter(
            QualityMetrics.calculated_at >= since_date,
            QualityMetrics.is_deleted == False
        ).group_by(
            func.date(QualityMetrics.calculated_at)
        ).order_by('date')

# Database session and connection management
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager

class DatabaseConfig:
    """Database configuration and session management."""
    
    def __init__(self, database_url: str, echo: bool = False):
        self.engine = create_engine(
            database_url,
            echo=echo,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.SessionLocal = scoped_session(sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        ))
    
    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all tables (use with caution!)."""
        Base.metadata.drop_all(bind=self.engine)
    
    @contextmanager
    def get_session(self):
        """Get database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session_factory(self):
        """Get session factory for dependency injection."""
        return self.SessionLocal

# Export all models and utilities
__all__ = [
    # Base classes
    'Base', 'BaseModel', 'SoftDeleteMixin', 'AuditMixin',
    
    # Enums
    'ProcessingStatus', 'TestClassification', 'ConfidenceLevel', 
    'QualityRating', 'ExecutionDifficulty',
    
    # Models
    'UserStory', 'TestCase', 'QualityMetrics', 'QAAnnotation',
    'LearningContribution', 'ExecutionFeedback', 'GroundTruthBenchmark',
    
    # Schemas
    'UserStorySchema', 'TestCaseSchema', 'TestStepSchema', 
    'QualityMetricsSchema', 'QAAnnotationSchema',
    
    # Utilities
    'DatabaseManager', 'ModelConverter', 'QueryBuilder', 'DatabaseConfig'
]