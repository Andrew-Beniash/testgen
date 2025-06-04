"""
Response Parser for OpenAI API Responses

This module handles parsing and validation of OpenAI API responses,
ensuring they match expected formats and extracting structured data.
"""

import json
import re
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, ValidationError
from enum import Enum

from app.core.config import settings


class ParsedTestCase(BaseModel):
    """Structured representation of a parsed test case."""
    title: str
    description: str
    prerequisites: List[str] = []
    test_steps: List[Dict[str, Any]] = []
    expected_final_result: str
    classification: str = "manual"
    priority: str = "medium"
    test_type: str = "functional"
    estimated_duration: int = 10  # minutes
    tags: List[str] = []
    persona: Optional[str] = None
    persona_context: Optional[str] = None
    permission_validations: List[str] = []
    cross_persona_interactions: List[str] = []


class ParsedResponse(BaseModel):
    """Complete parsed response from OpenAI."""
    test_cases: List[ParsedTestCase]
    summary: Dict[str, Any] = {}
    persona_test_cases: Dict[str, List[ParsedTestCase]] = {}
    cross_persona_scenarios: List[Dict[str, Any]] = []
    raw_content: str
    parsing_success: bool
    parsing_errors: List[str] = []
    confidence_score: float = 0.0


class ResponseParser:
    """Parses and validates OpenAI API responses."""
    
    def __init__(self):
        self.json_pattern = re.compile(r'```(?:json)?\s*(\{.*?\})\s*```', re.DOTALL | re.IGNORECASE)
        self.test_case_patterns = {
            'title': re.compile(r'(?:title|test case):?\s*(.+?)(?:\n|$)', re.IGNORECASE),
            'description': re.compile(r'(?:description|summary):?\s*(.+?)(?:\n|$)', re.IGNORECASE),
            'steps': re.compile(r'(?:steps|test steps):?\s*(.*?)(?:\n\n|\n(?=[A-Z])|$)', re.DOTALL | re.IGNORECASE),
            'expected': re.compile(r'(?:expected|expected result):?\s*(.+?)(?:\n|$)', re.IGNORECASE)
        }
    
    def parse_response(self, raw_response: str, expected_format: Dict[str, Any]) -> ParsedResponse:
        """Parse raw OpenAI response into structured format."""
        parsing_errors = []
        test_cases = []
        persona_test_cases = {}
        cross_persona_scenarios = []
        summary = {}
        
        try:
            # First, try to extract JSON from the response
            json_data = self._extract_json(raw_response)
            
            if json_data:
                # Parse structured JSON response
                test_cases, persona_test_cases, cross_persona_scenarios, summary = self._parse_json_response(
                    json_data, parsing_errors
                )
            else:
                # Fall back to text parsing
                test_cases = self._parse_text_response(raw_response, parsing_errors)
            
            # Validate and clean test cases
            validated_test_cases = self._validate_test_cases(test_cases, parsing_errors)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(validated_test_cases, parsing_errors)
            
            return ParsedResponse(
                test_cases=validated_test_cases,
                summary=summary,
                persona_test_cases=persona_test_cases,
                cross_persona_scenarios=cross_persona_scenarios,
                raw_content=raw_response,
                parsing_success=len(parsing_errors) == 0,
                parsing_errors=parsing_errors,
                confidence_score=confidence_score
            )
            
        except Exception as e:
            parsing_errors.append(f"Critical parsing error: {str(e)}")
            return ParsedResponse(
                test_cases=[],
                raw_content=raw_response,
                parsing_success=False,
                parsing_errors=parsing_errors,
                confidence_score=0.0
            )
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text response."""
        # Look for JSON code blocks
        json_matches = self.json_pattern.findall(text)
        
        for match in json_matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # Try to find JSON without code blocks
        try:
            # Look for content between { and } that might be JSON
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                potential_json = text[start_idx:end_idx + 1]
                return json.loads(potential_json)
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _parse_json_response(self, json_data: Dict[str, Any], parsing_errors: List[str]) -> tuple:
        """Parse structured JSON response."""
        test_cases = []
        persona_test_cases = {}
        cross_persona_scenarios = []
        summary = json_data.get('summary', {})
        
        # Parse standard test cases
        if 'test_cases' in json_data:
            for tc_data in json_data['test_cases']:
                try:
                    test_case = self._parse_test_case_data(tc_data)
                    test_cases.append(test_case)
                except Exception as e:
                    parsing_errors.append(f"Error parsing test case: {str(e)}")
        
        # Parse persona-based test cases
        if 'persona_test_cases' in json_data:
            for persona, cases in json_data['persona_test_cases'].items():
                persona_cases = []
                for tc_data in cases:
                    try:
                        test_case = self._parse_test_case_data(tc_data)
                        test_case.persona = persona
                        persona_cases.append(test_case)
                    except Exception as e:
                        parsing_errors.append(f"Error parsing persona test case for {persona}: {str(e)}")
                persona_test_cases[persona] = persona_cases
        
        # Parse cross-persona scenarios
        if 'cross_persona_scenarios' in json_data:
            cross_persona_scenarios = json_data['cross_persona_scenarios']
        
        return test_cases, persona_test_cases, cross_persona_scenarios, summary
    
    def _parse_test_case_data(self, tc_data: Dict[str, Any]) -> ParsedTestCase:
        """Parse individual test case data."""
        # Normalize test steps
        test_steps = []
        if 'test_steps' in tc_data:
            for i, step in enumerate(tc_data['test_steps']):
                if isinstance(step, dict):
                    test_steps.append({
                        'step_number': step.get('step_number', i + 1),
                        'action': step.get('action', ''),
                        'expected_result': step.get('expected_result', ''),
                        'test_data': step.get('test_data', {})
                    })
                elif isinstance(step, str):
                    test_steps.append({
                        'step_number': i + 1,
                        'action': step,
                        'expected_result': '',
                        'test_data': {}
                    })
        
        return ParsedTestCase(
            title=tc_data.get('title', 'Untitled Test Case'),
            description=tc_data.get('description', ''),
            prerequisites=tc_data.get('prerequisites', []),
            test_steps=test_steps,
            expected_final_result=tc_data.get('expected_final_result', ''),
            classification=tc_data.get('classification', 'manual'),
            priority=tc_data.get('priority', 'medium'),
            test_type=tc_data.get('test_type', 'functional'),
            estimated_duration=tc_data.get('estimated_duration', 10),
            tags=tc_data.get('tags', []),
            persona=tc_data.get('persona'),
            persona_context=tc_data.get('persona_context'),
            permission_validations=tc_data.get('permission_validations', []),
            cross_persona_interactions=tc_data.get('cross_persona_interactions', [])
        )
    
    def _parse_text_response(self, text: str, parsing_errors: List[str]) -> List[ParsedTestCase]:
        """Parse unstructured text response."""
        test_cases = []
        
        # Split text into potential test case sections
        sections = self._split_into_test_sections(text)
        
        for i, section in enumerate(sections):
            try:
                test_case = self._parse_text_section(section, i + 1)
                if test_case:
                    test_cases.append(test_case)
            except Exception as e:
                parsing_errors.append(f"Error parsing text section {i + 1}: {str(e)}")
        
        return test_cases
    
    def _split_into_test_sections(self, text: str) -> List[str]:
        """Split text into individual test case sections."""
        # Look for common test case delimiters
        delimiters = [
            r'(?:^|\n)(?:test case|tc)\s*\d+',
            r'(?:^|\n)#{1,3}\s*test',
            r'(?:^|\n)\d+\.\s*(?:test|verify)',
            r'(?:^|\n)\*\*(?:test|tc)',
        ]
        
        # Try each delimiter pattern
        for delimiter in delimiters:
            sections = re.split(delimiter, text, flags=re.IGNORECASE | re.MULTILINE)
            if len(sections) > 1:
                return [section.strip() for section in sections if section.strip()]
        
        # If no delimiters found, try to split by double newlines
        sections = text.split('\n\n')
        return [section.strip() for section in sections if len(section.strip()) > 50]
    
    def _parse_text_section(self, section: str, index: int) -> Optional[ParsedTestCase]:
        """Parse a single text section into a test case."""
        title_match = self.test_case_patterns['title'].search(section)
        description_match = self.test_case_patterns['description'].search(section)
        steps_match = self.test_case_patterns['steps'].search(section)
        expected_match = self.test_case_patterns['expected'].search(section)
        
        # Extract title
        title = title_match.group(1).strip() if title_match else f"Test Case {index}"
        
        # Extract description
        description = description_match.group(1).strip() if description_match else ""
        
        # Extract test steps
        test_steps = []
        if steps_match:
            steps_text = steps_match.group(1).strip()
            steps_lines = [line.strip() for line in steps_text.split('\n') if line.strip()]
            
            for i, step_line in enumerate(steps_lines):
                # Try to parse structured step
                step_parts = step_line.split(' - ')
                if len(step_parts) >= 2:
                    action = step_parts[0].strip()
                    expected = ' - '.join(step_parts[1:]).strip()
                else:
                    action = step_line
                    expected = ""
                
                test_steps.append({
                    'step_number': i + 1,
                    'action': action,
                    'expected_result': expected,
                    'test_data': {}
                })
        
        # Extract expected final result
        expected_final_result = expected_match.group(1).strip() if expected_match else ""
        
        # Extract classification from keywords
        classification = self._extract_classification(section)
        
        # Extract priority from keywords
        priority = self._extract_priority(section)
        
        if title or test_steps:
            return ParsedTestCase(
                title=title,
                description=description,
                test_steps=test_steps,
                expected_final_result=expected_final_result,
                classification=classification,
                priority=priority
            )
        
        return None
    
    def _extract_classification(self, text: str) -> str:
        """Extract automation classification from text."""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['api', 'endpoint', 'backend', 'service']):
            return 'api_automation'
        elif any(keyword in text_lower for keyword in ['ui', 'interface', 'browser', 'click', 'navigate']):
            return 'ui_automation'
        else:
            return 'manual'
    
    def _extract_priority(self, text: str) -> str:
        """Extract priority from text."""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['critical', 'high priority', 'urgent']):
            return 'high'
        elif any(keyword in text_lower for keyword in ['low priority', 'nice to have']):
            return 'low'
        else:
            return 'medium'
    
    def _validate_test_cases(self, test_cases: List[ParsedTestCase], parsing_errors: List[str]) -> List[ParsedTestCase]:
        """Validate and clean test cases."""
        validated_cases = []
        
        for i, test_case in enumerate(test_cases):
            try:
                # Basic validation
                if not test_case.title:
                    test_case.title = f"Test Case {i + 1}"
                
                if not test_case.description:
                    parsing_errors.append(f"Test case '{test_case.title}' missing description")
                
                if not test_case.test_steps:
                    parsing_errors.append(f"Test case '{test_case.title}' missing test steps")
                    continue
                
                # Validate classification
                valid_classifications = ['manual', 'api_automation', 'ui_automation']
                if test_case.classification not in valid_classifications:
                    test_case.classification = 'manual'
                
                # Validate priority
                valid_priorities = ['high', 'medium', 'low']
                if test_case.priority not in valid_priorities:
                    test_case.priority = 'medium'
                
                # Validate test type
                valid_types = ['functional', 'integration', 'boundary', 'negative', 'performance', 'security']
                if test_case.test_type not in valid_types:
                    test_case.test_type = 'functional'
                
                # Validate estimated duration
                if test_case.estimated_duration <= 0:
                    test_case.estimated_duration = 10
                
                validated_cases.append(test_case)
                
            except Exception as e:
                parsing_errors.append(f"Validation error for test case {i + 1}: {str(e)}")
        
        return validated_cases
    
    def _calculate_confidence_score(self, test_cases: List[ParsedTestCase], parsing_errors: List[str]) -> float:
        """Calculate confidence score for the parsing result."""
        if not test_cases:
            return 0.0
        
        total_score = 0.0
        max_score = len(test_cases) * 100
        
        for test_case in test_cases:
            case_score = 0
            
            # Title (20 points)
            if test_case.title and len(test_case.title) > 5:
                case_score += 20
            
            # Description (15 points)
            if test_case.description and len(test_case.description) > 10:
                case_score += 15
            
            # Test steps (30 points)
            if test_case.test_steps:
                step_score = min(30, len(test_case.test_steps) * 5)
                case_score += step_score
            
            # Expected result (15 points)
            if test_case.expected_final_result:
                case_score += 15
            
            # Classification (10 points)
            if test_case.classification in ['manual', 'api_automation', 'ui_automation']:
                case_score += 10
            
            # Priority (5 points)
            if test_case.priority in ['high', 'medium', 'low']:
                case_score += 5
            
            # Test type (5 points)
            if test_case.test_type:
                case_score += 5
            
            total_score += case_score
        
        # Penalty for parsing errors
        error_penalty = len(parsing_errors) * 10
        total_score = max(0, total_score - error_penalty)
        
        return min(1.0, total_score / max_score)
    
    def validate_response_format(self, response: str, expected_format: Dict[str, Any]) -> Dict[str, Any]:
        """Validate response against expected format."""
        validation_result = {
            'is_valid': False,
            'missing_fields': [],
            'format_errors': [],
            'structure_score': 0.0
        }
        
        try:
            json_data = self._extract_json(response)
            
            if not json_data:
                validation_result['format_errors'].append("No valid JSON found in response")
                return validation_result
            
            # Check required fields
            if 'test_cases' in expected_format:
                if 'test_cases' not in json_data:
                    validation_result['missing_fields'].append('test_cases')
                else:
                    # Validate test case structure
                    for i, tc in enumerate(json_data['test_cases']):
                        required_tc_fields = ['title', 'description', 'test_steps']
                        for field in required_tc_fields:
                            if field not in tc:
                                validation_result['missing_fields'].append(f'test_cases[{i}].{field}')
            
            # Calculate structure score
            total_fields = len(expected_format.keys())
            present_fields = len([k for k in expected_format.keys() if k in json_data])
            validation_result['structure_score'] = present_fields / total_fields if total_fields > 0 else 0.0
            
            # Overall validation
            validation_result['is_valid'] = (
                len(validation_result['missing_fields']) == 0 and
                len(validation_result['format_errors']) == 0 and
                validation_result['structure_score'] >= 0.8
            )
            
        except Exception as e:
            validation_result['format_errors'].append(f"Format validation error: {str(e)}")
        
        return validation_result


# Global response parser instance
response_parser = ResponseParser()
