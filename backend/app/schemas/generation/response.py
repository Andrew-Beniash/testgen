"""
Response schema definitions for test case generation.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class TestStep(BaseModel):
    """Test step with action and expected result."""
    step_number: int = Field(..., description="Step sequence number")
    action: str = Field(..., description="Test step action")
    expected_result: str = Field(..., description="Expected result after action")
    test_data: Optional[Dict[str, Any]] = Field(None, description="Test data for the step")


class QualityMetricsOutput(BaseModel):
    """Quality metrics for generated test case."""
    overall_score: float = Field(..., description="Overall quality score (0.0-1.0)")
    clarity_score: float = Field(..., description="Clarity score (0.0-1.0)")
    completeness_score: float = Field(..., description="Completeness score (0.0-1.0)")
    executability_score: float = Field(..., description="Executability score (0.0-1.0)")
    traceability_score: float = Field(..., description="Traceability score (0.0-1.0)")
    realism_score: float = Field(..., description="Realism score (0.0-1.0)")
    coverage_score: float = Field(..., description="Coverage score (0.0-1.0)")
    confidence_level: str = Field(..., description="Confidence level (low, medium, high)")
    quality_issues_count: int = Field(0, description="Number of quality issues identified")
    validation_passed: bool = Field(False, description="Whether the test case passed validation")


class ValidationIssue(BaseModel):
    """Validation issue details."""
    type: str = Field(..., description="Issue type")
    description: str = Field(..., description="Issue description")
    severity: str = Field(..., description="Issue severity (low, medium, high)")
    dimension: Optional[str] = Field(None, description="Affected quality dimension")


class GeneratedTestCase(BaseModel):
    """Generated test case with details and quality metrics."""
    id: Optional[str] = Field(None, description="Generated ID for the test case")
    title: str = Field(..., description="Test case title")
    description: str = Field(..., description="Test case description")
    steps: List[TestStep] = Field(..., description="Test case steps")
    test_type: str = Field(..., description="Test type (positive, negative, edge)")
    classification: str = Field(..., description="Classification (manual, api_automation, etc.)")
    classification_confidence: float = Field(..., description="Classification confidence score (0.0-1.0)")
    classification_reasoning: Optional[str] = Field(None, description="Reasoning for classification")
    priority: str = Field("medium", description="Test case priority (low, medium, high, critical)")
    estimated_duration: int = Field(..., description="Estimated duration in minutes")
    tags: List[str] = Field(default_factory=list, description="Tags for the test case")
    quality_metrics: QualityMetricsOutput = Field(..., description="Quality metrics")
    validation_issues: Optional[List[ValidationIssue]] = Field(None, description="Validation issues")
    preconditions: Optional[Dict[str, Any]] = Field(None, description="Prerequisites for test execution")
    postconditions: Optional[Dict[str, Any]] = Field(None, description="Expected state after test execution")
    persona: Optional[str] = Field(None, description="Target persona for the test case")
    test_data: Optional[Dict[str, Any]] = Field(None, description="Test data for the test case")


class GenerationSummary(BaseModel):
    """Summary of the generation process."""
    average_quality_score: float = Field(..., description="Average quality score of generated test cases")
    processing_time_seconds: float = Field(..., description="Processing time in seconds")
    quality_distribution: Dict[str, int] = Field(..., description="Distribution of quality scores")
    complexity_score: float = Field(..., description="Complexity score of the user story")
    coverage_analysis: Dict[str, Any] = Field(..., description="Coverage analysis of acceptance criteria")
    validation_summary: Dict[str, Any] = Field(..., description="Summary of validation results")


class GenerationResult(BaseModel):
    """Complete result of test case generation."""
    test_cases: List[GeneratedTestCase] = Field(..., description="Generated test cases")
    summary: GenerationSummary = Field(..., description="Generation summary")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
