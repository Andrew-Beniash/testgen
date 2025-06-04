"""
Main API router for v1 endpoints.

This module aggregates all v1 API routes and provides the main router
for the FastAPI application.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, test_cases, user_stories

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(test_cases.router, prefix="/test-cases", tags=["test-cases"])
api_router.include_router(user_stories.router, prefix="/user-stories", tags=["user-stories"])
