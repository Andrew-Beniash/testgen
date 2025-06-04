"""
Quality validation schema definitions.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum


class IssueType(str, Enum):
    """Issue type enumeration."""
    STRUCTURAL = "structural"  # Missing required fields, format issues
    CONTENT = "content"        # Language clarity, ambiguous text
    LOGICAL = "logical"        # Step sequence, dependency issues
    DOMAIN = "domain"          # Business rule violations
    EXECUTABILITY = "executability"  # Difficulties in test execution


class IssueSeverity(str, Enum):
    """Issue severity enumeration."""
    LOW = "low"         # Minor issues, not affecting functionality
    MEDIUM = "medium"   # Important issues to fix
    HIGH = "high"       # Critical issues blocking execution


class ValidationIssue(BaseModel):
    """Validation issue details."""
    type: IssueType = Field(..., description="Issue type")
    description: str = Field(..., description="Issue description")
    severity: IssueSeverity = Field(..., description="Issue severity")
    dimension: str = Field(..., description="Affected quality dimension")
    auto_fixable: bool = Field(False, description="Whether the issue can be auto-fixed")
    fix_suggestion: Optional[str] = Field(None, description="Suggestion for fixing the issue")
    affected_elements: Optional[List[str]] = Field(None, description="Affected elements (steps, fields)")


class ValidationResult(BaseModel):
    """Result of a validation check."""
    passed: bool = Field(..., description="Whether the validation passed")
    issues: List[ValidationIssue] = Field(default_factory=list, description="Validation issues")
    validator_name: str = Field(..., description="Name of the validator")
    validator_version: str = Field(..., description="Version of the validator")
    validation_timestamp: str = Field(..., description="Timestamp of validation")
    
    @property
    def has_issues(self) -> bool:
        """Check if validation has any issues."""
        return len(self.issues) > 0
    
    @property
    def has_high_severity_issues(self) -> bool:
        """Check if validation has high severity issues."""
        return any(issue.severity == IssueSeverity.HIGH for issue in self.issues)
    
    @property
    def has_auto_fixable_issues(self) -> bool:
        """Check if validation has auto-fixable issues."""
        return any(issue.auto_fixable for issue in self.issues)
    
    @property
    def issue_count_by_type(self) -> Dict[str, int]:
        """Get issue count by type."""
        return {
            issue_type.value: len([i for i in self.issues if i.type == issue_type])
            for issue_type in IssueType
        }
    
    @property
    def issue_count_by_severity(self) -> Dict[str, int]:
        """Get issue count by severity."""
        return {
            severity.value: len([i for i in self.issues if i.severity == severity])
            for severity in IssueSeverity
        }


class TestCaseValidationResult(BaseModel):
    """Validation result for a test case."""
    test_case_id: str = Field(..., description="Test case ID")
    validation_results: List[ValidationResult] = Field(..., description="Results from all validators")
    overall_passed: bool = Field(..., description="Whether all validations passed")
    auto_fixes_applied: List[Dict[str, Any]] = Field(default_factory=list, description="Auto-fixes that were applied")
    quality_impact: Optional[Dict[str, float]] = Field(None, description="Quality impact of validation")
    
    @property
    def total_issues(self) -> int:
        """Get total number of issues."""
        return sum(len(result.issues) for result in self.validation_results)
    
    @property
    def total_validators(self) -> int:
        """Get total number of validators run."""
        return len(self.validation_results)
    
    @property
    def passed_validators(self) -> int:
        """Get number of validators that passed."""
        return sum(1 for result in self.validation_results if result.passed)
    
    @property
    def all_issues(self) -> List[ValidationIssue]:
        """Get all issues from all validators."""
        return [issue for result in self.validation_results for issue in result.issues]
    
    @property
    def has_auto_fixable_issues(self) -> bool:
        """Check if there are auto-fixable issues."""
        return any(result.has_auto_fixable_issues for result in self.validation_results)
    
    @property
    def validation_summary(self) -> Dict[str, Any]:
        """Get a summary of validation results."""
        return {
            "passed": self.overall_passed,
            "total_validators": self.total_validators,
            "passed_validators": self.passed_validators,
            "total_issues": self.total_issues,
            "issues_by_type": {
                issue_type.value: len([i for i in self.all_issues if i.type == issue_type])
                for issue_type in IssueType
            },
            "issues_by_severity": {
                severity.value: len([i for i in self.all_issues if i.severity == severity])
                for severity in IssueSeverity
            },
            "auto_fixes_applied": len(self.auto_fixes_applied),
            "auto_fixable_issues": sum(1 for issue in self.all_issues if issue.auto_fixable)
        }


class MultiTestCaseValidationResult(BaseModel):
    """Validation results for multiple test cases."""
    results: Dict[str, TestCaseValidationResult] = Field(
        ..., description="Validation results by test case ID"
    )
    
    @property
    def passed_count(self) -> int:
        """Get number of test cases that passed validation."""
        return sum(1 for result in self.results.values() if result.overall_passed)
    
    @property
    def failed_count(self) -> int:
        """Get number of test cases that failed validation."""
        return len(self.results) - self.passed_count
    
    @property
    def auto_fixed_count(self) -> int:
        """Get number of test cases that had auto-fixes applied."""
        return sum(1 for result in self.results.values() if result.auto_fixes_applied)
    
    @property
    def total_issues(self) -> int:
        """Get total number of issues across all test cases."""
        return sum(result.total_issues for result in self.results.values())
    
    @property
    def validation_summary(self) -> Dict[str, Any]:
        """Get a summary of all validation results."""
        return {
            "total_test_cases": len(self.results),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "auto_fixed_count": self.auto_fixed_count,
            "total_issues": self.total_issues,
            "pass_rate": self.passed_count / len(self.results) if len(self.results) > 0 else 0.0,
            "issues_by_type": self._aggregate_issues_by_type(),
            "issues_by_severity": self._aggregate_issues_by_severity()
        }
    
    def _aggregate_issues_by_type(self) -> Dict[str, int]:
        """Aggregate issues by type across all test cases."""
        result = {issue_type.value: 0 for issue_type in IssueType}
        for validation_result in self.results.values():
            for issue in validation_result.all_issues:
                result[issue.type.value] += 1
        return result
    
    def _aggregate_issues_by_severity(self) -> Dict[str, int]:
        """Aggregate issues by severity across all test cases."""
        result = {severity.value: 0 for severity in IssueSeverity}
        for validation_result in self.results.values():
            for issue in validation_result.all_issues:
                result[issue.severity.value] += 1
        return result
