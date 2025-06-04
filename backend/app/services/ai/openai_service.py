"""
OpenAI Service for Test Case Generation

This module provides the main OpenAI integration service with quality-optimized
AI processing, retry logic, token tracking, and comprehensive error handling.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncGenerator
import logging
from dataclasses import dataclass
import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from openai import APIError, RateLimitError, APITimeoutError, APIConnectionError

from app.core.config import settings
from .prompt_manager import PromptManager, PromptContext, StoryDomain, StoryComplexity, TestGenerationType
from .token_tracker import TokenTracker, TokenUsage, ModelType
from .response_parser import ResponseParser, ParsedResponse

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class GenerationRequest:
    """Request for test case generation."""
    user_story_title: str
    user_story_description: str
    acceptance_criteria: str
    domain: Optional[StoryDomain] = None
    complexity: Optional[StoryComplexity] = None
    generation_type: TestGenerationType = TestGenerationType.STANDARD
    personas: Optional[List[str]] = None
    business_rules: Optional[List[str]] = None
    additional_context: Optional[Dict[str, Any]] = None
    max_test_cases: int = 12
    quality_threshold: float = 0.75


@dataclass
class GenerationResult:
    """Result of test case generation."""
    test_cases: List[Dict[str, Any]]
    persona_test_cases: Dict[str, List[Dict[str, Any]]]
    cross_persona_scenarios: List[Dict[str, Any]]
    summary: Dict[str, Any]
    quality_score: float
    confidence_score: float
    token_usage: TokenUsage
    processing_time: float
    generation_metadata: Dict[str, Any]
    success: bool
    error_message: Optional[str] = None


class RetryConfig:
    """Configuration for retry logic."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class OpenAIService:
    """Main OpenAI service for test case generation."""
    
    def __init__(
        self,
        prompt_manager: Optional[PromptManager] = None,
        token_tracker: Optional[TokenTracker] = None,
        response_parser: Optional[ResponseParser] = None
    ):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.prompt_manager = prompt_manager or PromptManager()
        self.token_tracker = token_tracker or TokenTracker()
        self.response_parser = response_parser or ResponseParser()
        self.retry_config = RetryConfig()
        
        # Generation parameters
        self.model = settings.OPENAI_MODEL
        self.max_tokens = settings.OPENAI_MAX_TOKENS
        self.temperature = settings.OPENAI_TEMPERATURE
        
        # Quality optimization parameters
        self.quality_focused_temperature = 0.1  # Lower temperature for more consistent quality
        self.creativity_temperature = 0.3       # Higher temperature for edge cases
        
        logger.info(f"OpenAI Service initialized with model: {self.model}")
    
    async def generate_test_cases(self, request: GenerationRequest) -> GenerationResult:
        """Generate test cases with quality assurance and retry logic."""
        start_time = time.time()
        
        try:
            # Detect domain if not provided
            if not request.domain:
                request.domain = await self._detect_domain(request.user_story_description)
            
            # Estimate complexity if not provided
            if not request.complexity:
                request.complexity = await self._estimate_complexity(request)
            
            # Create prompt context
            context = PromptContext(
                domain=request.domain,
                complexity=request.complexity,
                generation_type=request.generation_type,
                user_story_title=request.user_story_title,
                user_story_description=request.user_story_description,
                acceptance_criteria=request.acceptance_criteria,
                additional_context=request.additional_context,
                personas=request.personas,
                business_rules=request.business_rules
            )
            
            # Generate prompt
            prompt_data = self.prompt_manager.generate_prompt(context)
            
            # Adjust generation parameters based on context
            generation_params = self._adjust_generation_parameters(context, request)
            
            # Generate test cases with retry logic
            raw_response, token_usage = await self._generate_with_retry(
                prompt_data, generation_params
            )
            
            # Parse and validate response
            parsed_response = self.response_parser.parse_response(
                raw_response, prompt_data["expected_format"]
            )
            
            # If quality is below threshold, retry with enhanced prompt
            if parsed_response.confidence_score < request.quality_threshold:
                logger.warning(
                    f"Initial generation quality {parsed_response.confidence_score:.2f} "
                    f"below threshold {request.quality_threshold}. Retrying with enhanced prompt."
                )
                
                enhanced_response = await self._retry_with_enhanced_prompt(
                    context, request, parsed_response
                )
                if enhanced_response and enhanced_response.confidence_score > parsed_response.confidence_score:
                    parsed_response = enhanced_response
            
            # Track token usage
            await self.token_tracker.track_usage(token_usage)
            
            processing_time = time.time() - start_time
            
            # Build result
            result = GenerationResult(
                test_cases=self._convert_parsed_test_cases(parsed_response.test_cases),
                persona_test_cases=self._convert_persona_test_cases(parsed_response.persona_test_cases),
                cross_persona_scenarios=parsed_response.cross_persona_scenarios,
                summary=self._build_summary(parsed_response, request),
                quality_score=parsed_response.confidence_score,
                confidence_score=parsed_response.confidence_score,
                token_usage=token_usage,
                processing_time=processing_time,
                generation_metadata=self._build_generation_metadata(context, prompt_data, parsed_response),
                success=parsed_response.parsing_success,
                error_message=None
            )
            
            logger.info(
                f"Generated {len(result.test_cases)} test cases "
                f"with quality score {result.quality_score:.2f} "
                f"in {processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Test case generation failed: {str(e)}")
            
            return GenerationResult(
                test_cases=[],
                persona_test_cases={},
                cross_persona_scenarios=[],
                summary={},
                quality_score=0.0,
                confidence_score=0.0,
                token_usage=TokenUsage(
                    model=self.model, prompt_tokens=0, completion_tokens=0, total_tokens=0
                ),
                processing_time=processing_time,
                generation_metadata={},
                success=False,
                error_message=str(e)
            )
    
    async def _generate_with_retry(
        self, 
        prompt_data: Dict[str, Any], 
        generation_params: Dict[str, Any]
    ) -> tuple[str, TokenUsage]:
        """Generate response with retry logic."""
        last_exception = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                # Create messages
                messages = [
                    {"role": "system", "content": prompt_data["system_prompt"]},
                    {"role": "user", "content": prompt_data["user_prompt"]}
                ]
                
                # Make API call
                response: ChatCompletion = await self.client.chat.completions.create(
                    model=generation_params["model"],
                    messages=messages,
                    temperature=generation_params["temperature"],
                    max_tokens=generation_params["max_tokens"],
                    top_p=generation_params.get("top_p", 1.0),
                    frequency_penalty=generation_params.get("frequency_penalty", 0.0),
                    presence_penalty=generation_params.get("presence_penalty", 0.0)
                )
                
                # Extract response content
                content = response.choices[0].message.content
                
                # Create token usage record
                token_usage = TokenUsage(
                    model=self.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                    request_id=response.id
                )
                
                return content, token_usage
                
            except RateLimitError as e:
                last_exception = e
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt, base_delay=60.0)  # Longer delay for rate limits
                    logger.warning(f"Rate limit hit, retrying in {delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                
            except (APITimeoutError, APIConnectionError) as e:
                last_exception = e
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"API timeout/connection error, retrying in {delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                
            except APIError as e:
                last_exception = e
                if e.status_code and e.status_code >= 500 and attempt < self.retry_config.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    logger.warning(f"Server error {e.status_code}, retrying in {delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Client error or final attempt
                    break
        
        # If we get here, all retries failed
        raise last_exception or Exception("Generation failed after all retries")
    
    def _calculate_retry_delay(self, attempt: int, base_delay: Optional[float] = None) -> float:
        """Calculate delay for retry with exponential backoff and jitter."""
        base = base_delay or self.retry_config.base_delay
        delay = min(
            base * (self.retry_config.exponential_base ** attempt),
            self.retry_config.max_delay
        )
        
        if self.retry_config.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)  # Add 0-50% jitter
        
        return delay
    
    async def _detect_domain(self, description: str) -> StoryDomain:
        """Detect the domain of a user story based on keywords."""
        description_lower = description.lower()
        
        # Domain keyword mapping
        domain_keywords = {
            StoryDomain.ECOMMERCE: ['cart', 'checkout', 'product', 'order', 'payment', 'shop', 'buy', 'purchase'],
            StoryDomain.FINANCE: ['payment', 'transaction', 'account', 'balance', 'banking', 'credit', 'loan'],
            StoryDomain.HEALTHCARE: ['patient', 'medical', 'doctor', 'treatment', 'prescription', 'health', 'clinical'],
            StoryDomain.SAAS: ['subscription', 'tenant', 'dashboard', 'analytics', 'configuration', 'integration'],
            StoryDomain.MOBILE: ['mobile', 'app', 'touch', 'swipe', 'notification', 'offline', 'device'],
            StoryDomain.API: ['api', 'endpoint', 'service', 'webhook', 'integration', 'json', 'rest']
        }
        
        # Score each domain
        domain_scores = {}
        for domain, keywords in domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in description_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return StoryDomain.GENERAL
    
    async def _estimate_complexity(self, request: GenerationRequest) -> StoryComplexity:
        """Estimate complexity based on story characteristics."""
        complexity_score = 0.0
        
        # Analyze acceptance criteria complexity
        criteria_lines = len(request.acceptance_criteria.split('\n'))
        if criteria_lines > 10:
            complexity_score += 0.3
        elif criteria_lines > 5:
            complexity_score += 0.15
        
        # Analyze description complexity
        description_words = len(request.user_story_description.split())
        if description_words > 100:
            complexity_score += 0.2
        elif description_words > 50:
            complexity_score += 0.1
        
        # Check for integration keywords
        integration_keywords = ['integrate', 'api', 'service', 'external', 'third-party', 'webhook']
        if any(keyword in request.user_story_description.lower() for keyword in integration_keywords):
            complexity_score += 0.2
        
        # Check for multiple personas
        if request.personas and len(request.personas) > 2:
            complexity_score += 0.15
        
        # Check for business rules
        if request.business_rules and len(request.business_rules) > 3:
            complexity_score += 0.15
        
        # Determine complexity level
        if complexity_score >= 0.7:
            return StoryComplexity.COMPLEX
        elif complexity_score >= 0.3:
            return StoryComplexity.MEDIUM
        else:
            return StoryComplexity.SIMPLE
    
    def _adjust_generation_parameters(
        self, 
        context: PromptContext, 
        request: GenerationRequest
    ) -> Dict[str, Any]:
        """Adjust generation parameters based on context and requirements."""
        params = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        # Adjust temperature based on generation type
        if context.generation_type == TestGenerationType.EDGE_CASE_FOCUSED:
            params["temperature"] = self.creativity_temperature  # Higher for creativity
        elif context.generation_type == TestGenerationType.STANDARD:
            params["temperature"] = self.quality_focused_temperature  # Lower for consistency
        
        # Adjust max tokens based on complexity
        if context.complexity == StoryComplexity.COMPLEX:
            params["max_tokens"] = min(self.max_tokens * 1.5, 6000)
        elif context.complexity == StoryComplexity.SIMPLE:
            params["max_tokens"] = int(self.max_tokens * 0.7)
        
        # Adjust for persona-based generation
        if context.generation_type == TestGenerationType.PERSONA_BASED and context.personas:
            # More tokens needed for multiple personas
            persona_multiplier = 1 + (len(context.personas) * 0.2)
            params["max_tokens"] = int(params["max_tokens"] * persona_multiplier)
        
        return params
    
    async def _retry_with_enhanced_prompt(
        self,
        context: PromptContext,
        request: GenerationRequest,
        initial_response: ParsedResponse
    ) -> Optional[ParsedResponse]:
        """Retry generation with an enhanced prompt for better quality."""
        try:
            # Analyze issues with initial response
            quality_issues = []
            if len(initial_response.test_cases) < 3:
                quality_issues.append("insufficient test cases")
            if initial_response.parsing_errors:
                quality_issues.append("parsing errors")
            
            # Create enhanced context with quality feedback
            enhanced_context = context
            if not enhanced_context.additional_context:
                enhanced_context.additional_context = {}
            
            enhanced_context.additional_context.update({
                "quality_improvement_needed": True,
                "previous_issues": quality_issues,
                "minimum_test_cases": max(5, request.max_test_cases // 2),
                "focus_on_clarity": True
            })
            
            # Generate enhanced prompt
            enhanced_prompt = self.prompt_manager.generate_prompt(enhanced_context)
            
            # Add quality enhancement instructions to the prompt
            quality_enhancement = """

IMPORTANT: The previous generation had quality issues. Please ensure:
1. Generate at least 5 comprehensive test cases
2. Each test case has clear, specific steps
3. Include realistic test data
4. Provide detailed expected results
5. Use proper JSON formatting
6. Focus on practical, executable scenarios"""
            
            enhanced_prompt["user_prompt"] += quality_enhancement
            
            # Use slightly higher temperature for more variety
            enhanced_params = self._adjust_generation_parameters(enhanced_context, request)
            enhanced_params["temperature"] = min(enhanced_params["temperature"] + 0.1, 0.5)
            
            # Generate with enhanced prompt
            raw_response, token_usage = await self._generate_with_retry(
                enhanced_prompt, enhanced_params
            )
            
            # Parse enhanced response
            enhanced_response = self.response_parser.parse_response(
                raw_response, enhanced_prompt["expected_format"]
            )
            
            # Track additional token usage
            await self.token_tracker.track_usage(token_usage)
            
            return enhanced_response
            
        except Exception as e:
            logger.error(f"Enhanced prompt retry failed: {str(e)}")
            return None
    
    def _convert_parsed_test_cases(self, parsed_cases: List[Any]) -> List[Dict[str, Any]]:
        """Convert parsed test cases to API format."""
        result = []
        for case in parsed_cases:
            result.append({
                "title": case.title,
                "description": case.description,
                "prerequisites": case.prerequisites,
                "test_steps": case.test_steps,
                "expected_final_result": case.expected_final_result,
                "classification": case.classification,
                "priority": case.priority,
                "test_type": case.test_type,
                "estimated_duration": case.estimated_duration,
                "tags": case.tags
            })
        return result
    
    def _convert_persona_test_cases(
        self, 
        persona_cases: Dict[str, List[Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Convert persona test cases to API format."""
        result = {}
        for persona, cases in persona_cases.items():
            result[persona] = []
            for case in cases:
                case_dict = {
                    "title": case.title,
                    "description": case.description,
                    "persona": case.persona,
                    "persona_context": case.persona_context,
                    "prerequisites": case.prerequisites,
                    "test_steps": case.test_steps,
                    "expected_final_result": case.expected_final_result,
                    "permission_validations": case.permission_validations,
                    "cross_persona_interactions": case.cross_persona_interactions,
                    "classification": case.classification,
                    "priority": case.priority
                }
                result[persona].append(case_dict)
        return result
    
    def _build_summary(self, parsed_response: ParsedResponse, request: GenerationRequest) -> Dict[str, Any]:
        """Build summary information for the generation result."""
        total_test_cases = len(parsed_response.test_cases)
        persona_case_count = sum(len(cases) for cases in parsed_response.persona_test_cases.values())
        
        # Analyze classification distribution
        classifications = {}
        for case in parsed_response.test_cases:
            classification = case.classification
            classifications[classification] = classifications.get(classification, 0) + 1
        
        # Calculate automation ratio
        automated_count = sum(
            count for classification, count in classifications.items()
            if classification in ['api_automation', 'ui_automation']
        )
        automation_ratio = automated_count / total_test_cases if total_test_cases > 0 else 0.0
        
        return {
            "total_test_cases": total_test_cases,
            "persona_test_cases": persona_case_count,
            "cross_persona_scenarios": len(parsed_response.cross_persona_scenarios),
            "classification_distribution": classifications,
            "automation_ratio": automation_ratio,
            "average_estimated_duration": self._calculate_average_duration(parsed_response.test_cases),
            "coverage_areas": self._identify_coverage_areas(parsed_response.test_cases),
            "quality_score": parsed_response.confidence_score,
            "parsing_success": parsed_response.parsing_success,
            "parsing_errors_count": len(parsed_response.parsing_errors)
        }
    
    def _calculate_average_duration(self, test_cases: List[Any]) -> float:
        """Calculate average estimated duration for test cases."""
        if not test_cases:
            return 0.0
        
        total_duration = sum(case.estimated_duration for case in test_cases)
        return total_duration / len(test_cases)
    
    def _identify_coverage_areas(self, test_cases: List[Any]) -> List[str]:
        """Identify coverage areas from test cases."""
        coverage_areas = set()
        
        for case in test_cases:
            # Extract coverage areas from test types and tags
            coverage_areas.add(case.test_type)
            coverage_areas.update(case.tags)
            
            # Analyze title and description for coverage keywords
            content = f"{case.title} {case.description}".lower()
            
            if 'authentication' in content or 'login' in content:
                coverage_areas.add('authentication')
            if 'permission' in content or 'authorization' in content:
                coverage_areas.add('authorization')
            if 'data' in content or 'validation' in content:
                coverage_areas.add('data_validation')
            if 'error' in content or 'exception' in content:
                coverage_areas.add('error_handling')
            if 'performance' in content or 'load' in content:
                coverage_areas.add('performance')
            if 'security' in content:
                coverage_areas.add('security')
            if 'ui' in content or 'interface' in content:
                coverage_areas.add('user_interface')
            if 'api' in content or 'service' in content:
                coverage_areas.add('api_integration')
        
        return list(coverage_areas)
    
    def _build_generation_metadata(
        self,
        context: PromptContext,
        prompt_data: Dict[str, Any],
        parsed_response: ParsedResponse
    ) -> Dict[str, Any]:
        """Build metadata about the generation process."""
        return {
            "domain": context.domain.value,
            "complexity": context.complexity.value,
            "generation_type": context.generation_type.value,
            "template_used": prompt_data["template_name"],
            "estimated_prompt_tokens": prompt_data["estimated_tokens"],
            "parsing_confidence": parsed_response.confidence_score,
            "parsing_errors": parsed_response.parsing_errors,
            "generation_timestamp": datetime.utcnow().isoformat(),
            "model_used": self.model,
            "temperature_used": self.temperature
        }
    
    async def get_usage_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get usage statistics for the specified period."""
        stats = self.token_tracker.get_usage_stats(days)
        alerts = await self.token_tracker.get_cost_alert_status()
        optimization = self.token_tracker.optimize_token_usage()
        
        return {
            "period_days": days,
            "total_requests": stats.total_requests,
            "total_tokens": stats.total_tokens,
            "total_cost": stats.total_cost,
            "average_tokens_per_request": stats.average_tokens_per_request,
            "average_cost_per_request": stats.average_cost_per_request,
            "cost_alerts": alerts,
            "optimization_recommendations": optimization
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the OpenAI service."""
        try:
            start_time = time.time()
            
            # Test with a simple request
            test_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' if you can hear me."}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=test_messages,
                max_tokens=10,
                temperature=0.1
            )
            
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "model": self.model,
                "response_time": response_time,
                "response_content": response.choices[0].message.content,
                "token_usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model": self.model
            }


# Global OpenAI service instance
openai_service = OpenAIService()
