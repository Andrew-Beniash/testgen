"""
Request schema definitions for test case generation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator

class UserStoryInput(BaseModel):
    """User story input for test case generation."""
    title: str = Field(
        ..., 
        min_length=5, 
        max_length=200,
        description="User story title, should follow format: 'As a [role], I want [goal] so that [benefit]'"
    )
    description: str = Field(
        ..., 
        min_length=10, 
        max_length=5000,
        description="Detailed description of the user story functionality"
    )
    acceptance_criteria: str = Field(
        ..., 
        min_length=10, 
        max_length=3000,
        description="Acceptance criteria defining when the story is complete"
    )
    domain: Optional[str] = Field(
        None,
        description="Optional domain classification (e.g., ecommerce, finance, healthcare, saas)"
    )
    azure_devops_id: Optional[str] = Field(
        None,
        description="Azure DevOps ID for the user story if available"
    )

    @validator('title')
    def validate_title_format(cls, v):
        """Validate user story title format."""
        if not any([
            v.lower().startswith("as a "),
            v.lower().startswith("as an ")
        ]):
            raise ValueError("Title should follow format: 'As a [role], I want [goal] so that [benefit]'")
        return v


class GenerationOptions(BaseModel):
    """Options for test case generation."""
    include_personas: bool = Field(
        False,
        description="Generate persona-specific test cases"
    )
    include_performance: bool = Field(
        False,
        description="Include performance test scenarios"
    )
    quality_threshold: float = Field(
        0.75,
        ge=0.0,
        le=1.0,
        description="Minimum quality threshold for test cases (0.0-1.0)"
    )
    max_test_cases: int = Field(
        15,
        ge=1,
        le=50,
        description="Maximum number of test cases to generate"
    )
    test_types: Optional[List[str]] = Field(
        None,
        description="Types of tests to generate (positive, negative, edge)"
    )
    complexity_level: Optional[str] = Field(
        None,
        description="Override complexity analysis (simple, medium, complex)"
    )


class GenerationRequest(BaseModel):
    """Complete request for test case generation."""
    story: UserStoryInput
    options: Optional[GenerationOptions] = Field(
        default_factory=GenerationOptions,
        description="Generation options and parameters"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata for the generation request"
    )
