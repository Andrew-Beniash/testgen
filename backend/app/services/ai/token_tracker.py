"""
Token Usage Tracking and Cost Monitoring

This module tracks OpenAI API token usage and provides cost estimates
for monitoring and optimization purposes.
"""

import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import aioredis
from pydantic import BaseModel

from app.core.config import settings


class ModelType(str, Enum):
    """OpenAI model types with their pricing information."""
    GPT_4_TURBO = "gpt-4-turbo-preview"
    GPT_4 = "gpt-4"
    GPT_3_5_TURBO = "gpt-3.5-turbo"


@dataclass
class TokenUsage:
    """Token usage information for a single API call."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    request_id: Optional[str] = None
    timestamp: datetime = None
    estimated_cost: float = 0.0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        self.estimated_cost = self.calculate_cost()
    
    def calculate_cost(self) -> float:
        """Calculate estimated cost based on current OpenAI pricing."""
        # Pricing per 1K tokens (as of January 2024)
        pricing = {
            ModelType.GPT_4_TURBO: {"prompt": 0.01, "completion": 0.03},
            ModelType.GPT_4: {"prompt": 0.03, "completion": 0.06},
            ModelType.GPT_3_5_TURBO: {"prompt": 0.001, "completion": 0.002},
        }
        
        model_pricing = pricing.get(self.model, pricing[ModelType.GPT_4_TURBO])
        
        prompt_cost = (self.prompt_tokens / 1000) * model_pricing["prompt"]
        completion_cost = (self.completion_tokens / 1000) * model_pricing["completion"]
        
        return prompt_cost + completion_cost


class UsageStats(BaseModel):
    """Aggregated usage statistics."""
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    average_tokens_per_request: float = 0.0
    average_cost_per_request: float = 0.0
    period_start: datetime
    period_end: datetime


class TokenTracker:
    """Tracks token usage and provides cost monitoring."""
    
    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis_client = redis_client
        self._usage_history: List[TokenUsage] = []
        self._daily_usage: Dict[str, UsageStats] = {}
        
    async def track_usage(self, usage: TokenUsage) -> None:
        """Track a new token usage event."""
        self._usage_history.append(usage)
        
        # Update daily usage stats
        date_key = usage.timestamp.strftime("%Y-%m-%d")
        if date_key not in self._daily_usage:
            self._daily_usage[date_key] = UsageStats(
                period_start=usage.timestamp.replace(hour=0, minute=0, second=0, microsecond=0),
                period_end=usage.timestamp.replace(hour=23, minute=59, second=59, microsecond=999999)
            )
        
        daily_stats = self._daily_usage[date_key]
        daily_stats.total_requests += 1
        daily_stats.total_tokens += usage.total_tokens
        daily_stats.total_cost += usage.estimated_cost
        daily_stats.average_tokens_per_request = daily_stats.total_tokens / daily_stats.total_requests
        daily_stats.average_cost_per_request = daily_stats.total_cost / daily_stats.total_requests
        
        # Store in Redis if available
        if self.redis_client:
            await self._store_usage_in_redis(usage)
    
    async def _store_usage_in_redis(self, usage: TokenUsage) -> None:
        """Store usage data in Redis for persistence."""
        try:
            # Store individual usage record
            usage_key = f"token_usage:{usage.timestamp.strftime('%Y-%m-%d')}:{int(time.time())}"
            await self.redis_client.setex(
                usage_key,
                timedelta(days=30).total_seconds(),
                json.dumps(asdict(usage), default=str)
            )
            
            # Update daily aggregates
            daily_key = f"daily_usage:{usage.timestamp.strftime('%Y-%m-%d')}"
            await self.redis_client.hincrby(daily_key, "total_requests", 1)
            await self.redis_client.hincrbyfloat(daily_key, "total_tokens", usage.total_tokens)
            await self.redis_client.hincrbyfloat(daily_key, "total_cost", usage.estimated_cost)
            await self.redis_client.expire(daily_key, timedelta(days=90).total_seconds())
            
        except Exception as e:
            # Log error but don't fail the main operation
            print(f"Failed to store usage in Redis: {e}")
    
    def get_usage_stats(self, days: int = 7) -> UsageStats:
        """Get usage statistics for the specified number of days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_usage = [u for u in self._usage_history if u.timestamp >= cutoff_date]
        
        if not recent_usage:
            return UsageStats(
                period_start=cutoff_date,
                period_end=datetime.utcnow()
            )
        
        total_requests = len(recent_usage)
        total_tokens = sum(u.total_tokens for u in recent_usage)
        total_cost = sum(u.estimated_cost for u in recent_usage)
        
        return UsageStats(
            total_requests=total_requests,
            total_tokens=total_tokens,
            total_cost=total_cost,
            average_tokens_per_request=total_tokens / total_requests,
            average_cost_per_request=total_cost / total_requests,
            period_start=cutoff_date,
            period_end=datetime.utcnow()
        )
    
    def get_daily_usage(self, date: Optional[datetime] = None) -> Optional[UsageStats]:
        """Get usage statistics for a specific day."""
        if date is None:
            date = datetime.utcnow()
        
        date_key = date.strftime("%Y-%m-%d")
        return self._daily_usage.get(date_key)
    
    async def get_cost_alert_status(self, daily_limit: float = 50.0, monthly_limit: float = 1000.0) -> Dict[str, Any]:
        """Check if usage is approaching or exceeding cost limits."""
        today_stats = self.get_daily_usage()
        monthly_stats = self.get_usage_stats(days=30)
        
        alerts = {
            "daily_alert": False,
            "monthly_alert": False,
            "daily_usage": today_stats.total_cost if today_stats else 0.0,
            "monthly_usage": monthly_stats.total_cost,
            "daily_limit": daily_limit,
            "monthly_limit": monthly_limit,
            "daily_percentage": 0.0,
            "monthly_percentage": 0.0
        }
        
        if today_stats:
            alerts["daily_percentage"] = (today_stats.total_cost / daily_limit) * 100
            alerts["daily_alert"] = today_stats.total_cost >= daily_limit * 0.8  # Alert at 80%
        
        alerts["monthly_percentage"] = (monthly_stats.total_cost / monthly_limit) * 100
        alerts["monthly_alert"] = monthly_stats.total_cost >= monthly_limit * 0.8  # Alert at 80%
        
        return alerts
    
    def optimize_token_usage(self, target_reduction: float = 0.2) -> Dict[str, str]:
        """Provide recommendations for optimizing token usage."""
        recent_stats = self.get_usage_stats(days=7)
        
        recommendations = []
        
        if recent_stats.average_tokens_per_request > 2000:
            recommendations.append(
                "Consider reducing prompt length or using more specific prompts to reduce token usage."
            )
        
        if recent_stats.total_cost > 10.0:  # $10 per week
            recommendations.append(
                "High weekly costs detected. Consider using gpt-3.5-turbo for simpler tasks."
            )
        
        # Analyze token distribution
        recent_usage = [u for u in self._usage_history if u.timestamp >= datetime.utcnow() - timedelta(days=7)]
        if recent_usage:
            avg_prompt_tokens = sum(u.prompt_tokens for u in recent_usage) / len(recent_usage)
            avg_completion_tokens = sum(u.completion_tokens for u in recent_usage) / len(recent_usage)
            
            if avg_prompt_tokens > avg_completion_tokens * 2:
                recommendations.append(
                    "Prompt tokens are significantly higher than completion tokens. "
                    "Consider optimizing prompt templates."
                )
        
        return {
            "current_weekly_cost": f"${recent_stats.total_cost:.2f}",
            "target_weekly_cost": f"${recent_stats.total_cost * (1 - target_reduction):.2f}",
            "recommendations": recommendations
        }


# Global token tracker instance
token_tracker = TokenTracker()
