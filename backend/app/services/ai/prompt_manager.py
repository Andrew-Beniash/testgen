"""
Prompt Management for Test Case Generation

This module provides domain-specific prompt templates and adaptive 
prompt engineering capabilities for different story types and contexts.
"""

import json
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass
from jinja2 import Template, Environment, BaseLoader
from pydantic import BaseModel

from app.core.config import settings


class StoryDomain(str, Enum):
    """Different domains for user stories."""
    ECOMMERCE = "ecommerce"
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    SAAS = "saas"
    MOBILE = "mobile"
    API = "api"
    GENERAL = "general"


class StoryComplexity(str, Enum):
    """Complexity levels for user stories."""
    SIMPLE = "simple"       # 0.0 - 0.3
    MEDIUM = "medium"       # 0.3 - 0.7
    COMPLEX = "complex"     # 0.7 - 1.0


class TestGenerationType(str, Enum):
    """Types of test generation approaches."""
    STANDARD = "standard"
    PERSONA_BASED = "persona_based"
    EDGE_CASE_FOCUSED = "edge_case_focused"
    PERFORMANCE_FOCUSED = "performance_focused"
    SECURITY_FOCUSED = "security_focused"


@dataclass
class PromptContext:
    """Context information for prompt generation."""
    domain: StoryDomain
    complexity: StoryComplexity
    generation_type: TestGenerationType
    user_story_title: str
    user_story_description: str
    acceptance_criteria: str
    additional_context: Optional[Dict[str, Any]] = None
    personas: Optional[List[str]] = None
    business_rules: Optional[List[str]] = None


class PromptTemplate(BaseModel):
    """Template for generating AI prompts."""
    name: str
    domain: StoryDomain
    complexity: StoryComplexity
    generation_type: TestGenerationType
    system_prompt: str
    user_prompt_template: str
    expected_output_format: Dict[str, Any]
    quality_criteria: List[str]
    token_estimate: int
    version: str = "1.0"


class PromptManager:
    """Manages prompt templates and generates optimized prompts."""
    
    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self.jinja_env = Environment(loader=BaseLoader())
        self._load_default_templates()
        
    def _load_default_templates(self):
        """Load default prompt templates for different domains and types."""
        
        # Standard E-commerce Template
        self.templates["ecommerce_standard"] = PromptTemplate(
            name="E-commerce Standard Test Generation",
            domain=StoryDomain.ECOMMERCE,
            complexity=StoryComplexity.MEDIUM,
            generation_type=TestGenerationType.STANDARD,
            system_prompt=self._get_ecommerce_system_prompt(),
            user_prompt_template=self._get_standard_user_prompt_template(),
            expected_output_format=self._get_standard_output_format(),
            quality_criteria=self._get_ecommerce_quality_criteria(),
            token_estimate=1200
        )
        
        # Finance Domain Template
        self.templates["finance_standard"] = PromptTemplate(
            name="Finance Standard Test Generation",
            domain=StoryDomain.FINANCE,
            complexity=StoryComplexity.MEDIUM,
            generation_type=TestGenerationType.STANDARD,
            system_prompt=self._get_finance_system_prompt(),
            user_prompt_template=self._get_standard_user_prompt_template(),
            expected_output_format=self._get_standard_output_format(),
            quality_criteria=self._get_finance_quality_criteria(),
            token_estimate=1300
        )
        
        # Healthcare Domain Template
        self.templates["healthcare_standard"] = PromptTemplate(
            name="Healthcare Standard Test Generation",
            domain=StoryDomain.HEALTHCARE,
            complexity=StoryComplexity.MEDIUM,
            generation_type=TestGenerationType.STANDARD,
            system_prompt=self._get_healthcare_system_prompt(),
            user_prompt_template=self._get_standard_user_prompt_template(),
            expected_output_format=self._get_standard_output_format(),
            quality_criteria=self._get_healthcare_quality_criteria(),
            token_estimate=1400
        )
        
        # SaaS Domain Template
        self.templates["saas_standard"] = PromptTemplate(
            name="SaaS Standard Test Generation",
            domain=StoryDomain.SAAS,
            complexity=StoryComplexity.MEDIUM,
            generation_type=TestGenerationType.STANDARD,
            system_prompt=self._get_saas_system_prompt(),
            user_prompt_template=self._get_standard_user_prompt_template(),
            expected_output_format=self._get_standard_output_format(),
            quality_criteria=self._get_saas_quality_criteria(),
            token_estimate=1100
        )
        
        # Persona-based Template
        self.templates["persona_based"] = PromptTemplate(
            name="Persona-based Test Generation",
            domain=StoryDomain.GENERAL,
            complexity=StoryComplexity.MEDIUM,
            generation_type=TestGenerationType.PERSONA_BASED,
            system_prompt=self._get_persona_system_prompt(),
            user_prompt_template=self._get_persona_user_prompt_template(),
            expected_output_format=self._get_persona_output_format(),
            quality_criteria=self._get_persona_quality_criteria(),
            token_estimate=1500
        )
        
        # Edge Case Focused Template
        self.templates["edge_case_focused"] = PromptTemplate(
            name="Edge Case Focused Test Generation",
            domain=StoryDomain.GENERAL,
            complexity=StoryComplexity.COMPLEX,
            generation_type=TestGenerationType.EDGE_CASE_FOCUSED,
            system_prompt=self._get_edge_case_system_prompt(),
            user_prompt_template=self._get_edge_case_user_prompt_template(),
            expected_output_format=self._get_standard_output_format(),
            quality_criteria=self._get_edge_case_quality_criteria(),
            token_estimate=1600
        )
    
    def get_optimal_template(self, context: PromptContext) -> PromptTemplate:
        """Get the most appropriate template for the given context."""
        # Try to find exact match
        key = f"{context.domain.value}_{context.generation_type.value}"
        if key in self.templates:
            return self.templates[key]
        
        # Fall back to domain-specific standard template
        domain_key = f"{context.domain.value}_standard"
        if domain_key in self.templates:
            return self.templates[domain_key]
        
        # Fall back to generation type template
        if context.generation_type.value in self.templates:
            return self.templates[context.generation_type.value]
        
        # Final fallback to SaaS standard (most general)
        return self.templates["saas_standard"]
    
    def generate_prompt(self, context: PromptContext) -> Dict[str, Any]:
        """Generate a complete prompt from context."""
        template = self.get_optimal_template(context)
        
        # Render user prompt with context
        user_template = self.jinja_env.from_string(template.user_prompt_template)
        user_prompt = user_template.render(
            title=context.user_story_title,
            description=context.user_story_description,
            acceptance_criteria=context.acceptance_criteria,
            domain=context.domain.value,
            complexity=context.complexity.value,
            personas=context.personas or [],
            business_rules=context.business_rules or [],
            additional_context=context.additional_context or {}
        )
        
        return {
            "system_prompt": template.system_prompt,
            "user_prompt": user_prompt,
            "expected_format": template.expected_output_format,
            "quality_criteria": template.quality_criteria,
            "template_name": template.name,
            "estimated_tokens": template.token_estimate
        }
    
    # System prompts for different domains
    def _get_ecommerce_system_prompt(self) -> str:
        return """You are an expert QA engineer specializing in e-commerce testing. Generate comprehensive, realistic test cases that cover:

1. User authentication and account management
2. Product catalog browsing and search
3. Shopping cart functionality
4. Checkout and payment processing
5. Order management and tracking
6. Customer service interactions
7. Mobile responsiveness
8. Security and data protection

Focus on real-world scenarios including edge cases, error conditions, and cross-browser compatibility. Consider different user personas (new customers, returning customers, mobile users) and payment methods. Ensure test cases are specific, executable, and include realistic test data."""
    
    def _get_finance_system_prompt(self) -> str:
        return """You are an expert QA engineer specializing in financial services testing. Generate comprehensive, compliant test cases that cover:

1. Account management and authentication
2. Transaction processing and validation
3. Regulatory compliance (PCI DSS, SOX, etc.)
4. Security and fraud prevention
5. Reporting and audit trails
6. Data privacy and encryption
7. Multi-factor authentication
8. Real-time processing requirements

Emphasize security, accuracy, and compliance. Include test cases for boundary conditions, data validation, and error handling. Consider different user roles (customers, administrators, auditors) and ensure test cases verify regulatory requirements."""
    
    def _get_healthcare_system_prompt(self) -> str:
        return """You are an expert QA engineer specializing in healthcare IT testing. Generate comprehensive, HIPAA-compliant test cases that cover:

1. Patient data management and privacy
2. Electronic health records (EHR) functionality
3. Clinical workflow support
4. Integration with medical devices
5. Prescription and medication management
6. Appointment scheduling and management
7. Insurance and billing processes
8. Audit trails and compliance reporting

Prioritize patient safety, data security, and regulatory compliance (HIPAA, FDA, HL7). Include test cases for data validation, access controls, and integration scenarios. Consider different user roles (patients, doctors, nurses, administrators)."""
    
    def _get_saas_system_prompt(self) -> str:
        return """You are an expert QA engineer specializing in SaaS application testing. Generate comprehensive test cases that cover:

1. User authentication and authorization
2. Multi-tenancy and data isolation
3. API functionality and integration
4. Subscription and billing management
5. Performance and scalability
6. Data backup and recovery
7. Configuration and customization
8. Analytics and reporting

Focus on cloud-native concerns including scalability, security, and multi-tenant architecture. Include test cases for API endpoints, user permissions, and data isolation. Consider different subscription tiers and user roles."""
    
    def _get_persona_system_prompt(self) -> str:
        return """You are an expert QA engineer specializing in persona-based testing. Generate test cases from the perspective of different user personas, ensuring comprehensive coverage of:

1. Role-specific workflows and permissions
2. User experience variations by persona
3. Accessibility requirements
4. Device and platform preferences
5. Business process variations
6. Cross-persona interactions
7. Permission boundaries and security
8. Persona-specific edge cases

Create realistic scenarios that reflect how different users would actually interact with the system. Include test cases for permission validation, workflow variations, and cross-persona collaboration."""
    
    def _get_edge_case_system_prompt(self) -> str:
        return """You are an expert QA engineer specializing in edge case and boundary testing. Generate comprehensive test cases that cover:

1. Boundary value analysis
2. Error conditions and exception handling
3. Data validation limits
4. Concurrent user scenarios
5. System resource limitations
6. Network and connectivity issues
7. Integration failure scenarios
8. Performance under stress

Focus on scenarios that could break the system or reveal hidden defects. Include test cases for maximum/minimum values, null/empty inputs, special characters, and system limits. Emphasize negative testing and error recovery."""
    
    # User prompt templates
    def _get_standard_user_prompt_template(self) -> str:
        return """Generate comprehensive test cases for the following user story:

**Title:** {{ title }}

**Description:** {{ description }}

**Acceptance Criteria:**
{{ acceptance_criteria }}

**Domain:** {{ domain }}
**Complexity:** {{ complexity }}

{% if business_rules %}
**Business Rules:**
{% for rule in business_rules %}
- {{ rule }}
{% endfor %}
{% endif %}

{% if additional_context %}
**Additional Context:**
{% for key, value in additional_context.items() %}
- {{ key }}: {{ value }}
{% endfor %}
{% endif %}

Generate 5-12 test cases that provide comprehensive coverage including:
1. Happy path scenarios
2. Alternative flows
3. Edge cases and boundary conditions
4. Error scenarios and validation
5. Integration scenarios

Each test case should include:
- Clear, descriptive title
- Detailed test steps
- Expected results
- Test data (realistic and specific)
- Prerequisites/preconditions
- Automation classification (manual, api_automation, ui_automation)

Ensure test cases are specific, executable, and include realistic test data."""
    
    def _get_persona_user_prompt_template(self) -> str:
        return """Generate persona-specific test cases for the following user story:

**Title:** {{ title }}

**Description:** {{ description }}

**Acceptance Criteria:**
{{ acceptance_criteria }}

**Target Personas:**
{% for persona in personas %}
- {{ persona }}
{% endfor %}

For each persona, generate test cases that reflect their specific:
- Workflow patterns and preferences
- Permission levels and access rights
- Device/platform usage patterns
- Experience level and technical proficiency
- Business objectives and priorities

Include cross-persona scenarios where personas interact or collaborate.

Each test case should include:
- Persona designation
- Role-specific context
- Detailed test steps
- Expected results
- Permission validations
- Realistic test data for that persona type"""
    
    def _get_edge_case_user_prompt_template(self) -> str:
        return """Generate edge case and boundary test cases for the following user story:

**Title:** {{ title }}

**Description:** {{ description }}

**Acceptance Criteria:**
{{ acceptance_criteria }}

Focus specifically on:
1. Boundary value analysis (min/max values, limits)
2. Invalid input scenarios
3. System constraint testing
4. Concurrent access scenarios
5. Data corruption/recovery scenarios
6. Integration failure points
7. Performance edge cases
8. Security boundary testing

Generate test cases that push the system to its limits and test error handling, recovery mechanisms, and system resilience.

Each test case should include:
- Specific boundary or edge condition being tested
- Detailed steps to reproduce the condition
- Expected error handling or system response
- Recovery/cleanup procedures
- Risk level assessment"""
    
    # Output formats
    def _get_standard_output_format(self) -> Dict[str, Any]:
        return {
            "test_cases": [
                {
                    "title": "string",
                    "description": "string",
                    "prerequisites": ["string"],
                    "test_steps": [
                        {
                            "step_number": "integer",
                            "action": "string",
                            "expected_result": "string",
                            "test_data": "object"
                        }
                    ],
                    "expected_final_result": "string",
                    "classification": "manual|api_automation|ui_automation",
                    "priority": "high|medium|low",
                    "test_type": "functional|integration|boundary|negative",
                    "estimated_duration": "integer (minutes)",
                    "tags": ["string"]
                }
            ],
            "summary": {
                "total_test_cases": "integer",
                "coverage_areas": ["string"],
                "automation_ratio": "float"
            }
        }
    
    def _get_persona_output_format(self) -> Dict[str, Any]:
        return {
            "persona_test_cases": {
                "persona_name": [
                    {
                        "title": "string",
                        "description": "string",
                        "persona": "string",
                        "persona_context": "string",
                        "prerequisites": ["string"],
                        "test_steps": [
                            {
                                "step_number": "integer",
                                "action": "string",
                                "expected_result": "string",
                                "persona_specific_notes": "string"
                            }
                        ],
                        "permission_validations": ["string"],
                        "cross_persona_interactions": ["string"],
                        "classification": "manual|api_automation|ui_automation",
                        "priority": "high|medium|low"
                    }
                ]
            },
            "cross_persona_scenarios": [
                {
                    "title": "string",
                    "involved_personas": ["string"],
                    "scenario_description": "string",
                    "test_steps": ["object"]
                }
            ]
        }
    
    # Quality criteria for different domains
    def _get_ecommerce_quality_criteria(self) -> List[str]:
        return [
            "Test cases cover the complete customer journey from browsing to order completion",
            "Payment processing scenarios include multiple payment methods and error conditions", 
            "Security test cases verify data protection and fraud prevention",
            "Mobile responsiveness and cross-browser compatibility are validated",
            "Inventory management and stock validation scenarios are included",
            "Customer account management and authentication flows are comprehensive",
            "Test data includes realistic product information and user data"
        ]
    
    def _get_finance_quality_criteria(self) -> List[str]:
        return [
            "All test cases verify security and compliance requirements",
            "Transaction processing includes validation and audit trail verification",
            "Data encryption and privacy protection scenarios are comprehensive",
            "Error handling and recovery procedures are clearly defined",
            "Regulatory compliance validation is included in relevant test cases",
            "Multi-factor authentication scenarios are thorough",
            "Boundary testing includes financial limits and constraints"
        ]
    
    def _get_healthcare_quality_criteria(self) -> List[str]:
        return [
            "Patient data privacy and HIPAA compliance are verified in all scenarios",
            "Clinical workflow integration is validated with realistic medical scenarios",
            "Access control and permission management is comprehensive",
            "Data integrity and accuracy validation is included",
            "Integration with medical devices and systems is tested",
            "Audit trail and compliance reporting scenarios are complete",
            "Emergency and critical care scenarios are appropriately prioritized"
        ]
    
    def _get_saas_quality_criteria(self) -> List[str]:
        return [
            "Multi-tenancy and data isolation are verified in all scenarios",
            "API functionality includes authentication and rate limiting tests",
            "Subscription and billing scenarios cover all plan types",
            "Performance and scalability concerns are addressed",
            "Integration scenarios cover third-party services and webhooks",
            "User permission and role management is comprehensive",
            "Backup and recovery procedures are validated"
        ]
    
    def _get_persona_quality_criteria(self) -> List[str]:
        return [
            "Each persona has distinct test scenarios reflecting their role",
            "Permission boundaries are validated for each persona type",
            "Cross-persona interactions and collaborations are tested",
            "Workflow variations by persona are clearly documented",
            "Accessibility requirements are addressed for relevant personas",
            "Device and platform preferences are reflected in test scenarios",
            "Business objective alignment is validated for each persona"
        ]
    
    def _get_edge_case_quality_criteria(self) -> List[str]:
        return [
            "Boundary value analysis covers minimum and maximum constraints",
            "Error handling and recovery mechanisms are thoroughly tested",
            "Concurrent access and race condition scenarios are included",
            "System resource limitation testing is comprehensive",
            "Data corruption and recovery scenarios are validated",
            "Integration failure points and fallback mechanisms are tested",
            "Performance under stress conditions is evaluated"
        ]
    
    def add_custom_template(self, template: PromptTemplate) -> None:
        """Add a custom prompt template."""
        key = f"{template.domain.value}_{template.generation_type.value}"
        self.templates[key] = template
    
    def update_template_from_feedback(self, template_name: str, feedback_data: Dict[str, Any]) -> None:
        """Update template based on feedback and learning."""
        # This would integrate with the learning system to improve prompts
        # Implementation would analyze feedback patterns and optimize templates
        pass
    
    def get_template_performance_metrics(self, template_name: str) -> Dict[str, Any]:
        """Get performance metrics for a specific template."""
        # This would return metrics like quality scores, token usage, success rate
        return {
            "average_quality_score": 0.0,
            "average_token_usage": 0,
            "success_rate": 0.0,
            "usage_count": 0
        }


# Global prompt manager instance
prompt_manager = PromptManager()
