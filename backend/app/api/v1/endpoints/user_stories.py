"""
User Stories API endpoints.

This module provides CRUD endpoints for user story management with
comprehensive validation, filtering, and error handling.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog
import uuid
from datetime import datetime

from app.api.v1.dependencies import (
    get_database_session,
    rate_limit_dependency,
    validate_pagination
)
from app.models.user_story import UserStory, ProcessingStatus
from app.schemas.generation.request import UserStoryInput

logger = structlog.get_logger(__name__)

router = APIRouter()


class UserStoryCreate(UserStoryInput):
    """Schema for creating a user story."""
    pass


class UserStoryUpdate(UserStoryInput):
    """Schema for updating a user story."""
    title: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    domain: Optional[str] = None


class UserStoryResponse(UserStoryInput):
    """Schema for user story response."""
    id: int
    azure_devops_id: str
    complexity_score: Optional[float] = None
    complexity_level: str
    domain_classification: Optional[str] = None
    processing_status: str
    is_processed: bool
    needs_processing: bool
    is_active: bool
    total_test_cases: int
    days_since_created: int
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_user_story(
    story_data: UserStoryCreate,
    db: AsyncSession = Depends(get_database_session),
    _rate_limit: None = Depends(rate_limit_dependency())
) -> Dict[str, Any]:
    """
    Create a new user story.
    
    Args:
        story_data: User story data
        db: Database session
        
    Returns:
        Dict containing created user story details
        
    Raises:
        HTTPException: If creation fails or validation errors occur
    """
    try:
        logger.info("Creating user story", title=story_data.title)
        
        # Check if Azure DevOps ID already exists
        if story_data.azure_devops_id:
            result = await db.execute(
                select(UserStory).where(
                    UserStory.azure_devops_id == story_data.azure_devops_id,
                    UserStory.is_deleted == False
                )
            )
            existing_story = result.scalar_one_or_none()
            
            if existing_story:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User story with Azure DevOps ID '{story_data.azure_devops_id}' already exists"
                )
        
        # Create new user story
        user_story = UserStory(
            azure_devops_id=story_data.azure_devops_id or f"manual_{uuid.uuid4()}",
            title=story_data.title,
            description=story_data.description,
            acceptance_criteria=story_data.acceptance_criteria,
            domain_classification=story_data.domain,
            processing_status=ProcessingStatus.PENDING,
            created_by="api_user"
        )
        
        # Validate content before saving
        validation_errors = user_story.validate_content()
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed: {'; '.join(validation_errors)}"
            )
        
        db.add(user_story)
        await db.commit()
        await db.refresh(user_story)
        
        # Convert to response format
        response_data = user_story.to_dict(include_relationships=False, include_sensitive=False)
        
        logger.info(
            "User story created successfully",
            user_story_id=user_story.id,
            azure_devops_id=user_story.azure_devops_id
        )
        
        return response_data
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to create user story", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user story: {str(e)}"
        )


@router.get("/{user_story_id}", response_model=Dict[str, Any])
async def get_user_story(
    user_story_id: int,
    include_test_cases: bool = Query(False, description="Include associated test cases"),
    include_relationships: bool = Query(False, description="Include all related objects"),
    db: AsyncSession = Depends(get_database_session)
) -> Dict[str, Any]:
    """
    Get a specific user story by ID.
    
    Args:
        user_story_id: User story ID
        include_test_cases: Whether to include test cases
        include_relationships: Whether to include all related objects
        db: Database session
        
    Returns:
        Dict containing user story details
        
    Raises:
        HTTPException: If user story not found
    """
    try:
        logger.info("Retrieving user story", user_story_id=user_story_id)
        
        # Build query with optional relationships
        query = select(UserStory).where(
            UserStory.id == user_story_id,
            UserStory.is_deleted == False
        )
        
        if include_test_cases or include_relationships:
            query = query.options(selectinload(UserStory.test_cases))
        
        if include_relationships:
            query = query.options(
                selectinload(UserStory.generation_statistics),
                selectinload(UserStory.ground_truth_benchmarks)
            )
        
        result = await db.execute(query)
        user_story = result.scalar_one_or_none()
        
        if not user_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User story with ID {user_story_id} not found"
            )
        
        # Convert to dictionary with requested inclusions
        response_data = user_story.to_dict(
            include_relationships=include_relationships,
            include_sensitive=False
        )
        
        logger.info("User story retrieved successfully", user_story_id=user_story_id)
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve user story", user_story_id=user_story_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user story: {str(e)}"
        )


@router.get("", response_model=Dict[str, Any])
async def list_user_stories(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    status: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    domain: Optional[str] = Query(None, description="Filter by domain classification"),
    search: Optional[str] = Query(None, description="Search in title, description, and acceptance criteria"),
    complexity_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum complexity score"),
    complexity_max: Optional[float] = Query(None, ge=0.0, le=1.0, description="Maximum complexity score"),
    include_test_cases: bool = Query(False, description="Include test case counts"),
    db: AsyncSession = Depends(get_database_session)
) -> Dict[str, Any]:
    """
    List user stories with filtering and pagination.
    
    Args:
        skip: Number of records to skip
        limit: Number of records to return
        status: Filter by processing status
        domain: Filter by domain classification
        search: Search term for title/description/acceptance criteria
        complexity_min: Minimum complexity score
        complexity_max: Maximum complexity score
        include_test_cases: Include test case information
        db: Database session
        
    Returns:
        Dict containing user stories and pagination info
    """
    try:
        # Validate pagination
        skip, limit = await validate_pagination(skip, limit)
        
        # Validate complexity range
        if complexity_min is not None and complexity_max is not None:
            if complexity_min > complexity_max:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="complexity_min cannot be greater than complexity_max"
                )
        
        logger.info(
            "Listing user stories",
            skip=skip,
            limit=limit,
            status=status,
            domain=domain,
            search=search,
            complexity_min=complexity_min,
            complexity_max=complexity_max
        )
        
        # Build base query
        query = select(UserStory).where(UserStory.is_deleted == False)
        count_query = select(func.count(UserStory.id)).where(UserStory.is_deleted == False)
        
        # Apply filters
        if status:
            query = query.where(UserStory.processing_status == status)
            count_query = count_query.where(UserStory.processing_status == status)
        
        if domain:
            query = query.where(UserStory.domain_classification == domain)
            count_query = count_query.where(UserStory.domain_classification == domain)
        
        if search:
            search_filter = (
                UserStory.title.ilike(f"%{search}%") |
                UserStory.description.ilike(f"%{search}%") |
                UserStory.acceptance_criteria.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        if complexity_min is not None:
            query = query.where(UserStory.complexity_score >= complexity_min)
            count_query = count_query.where(UserStory.complexity_score >= complexity_min)
        
        if complexity_max is not None:
            query = query.where(UserStory.complexity_score <= complexity_max)
            count_query = count_query.where(UserStory.complexity_score <= complexity_max)
        
        # Add optional relationships
        if include_test_cases:
            query = query.options(selectinload(UserStory.test_cases))
        
        # Apply pagination and ordering
        query = query.order_by(UserStory.created_at.desc()).offset(skip).limit(limit)
        
        # Execute queries
        result = await db.execute(query)
        user_stories = result.scalars().all()
        
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # Convert to dictionaries
        user_stories_data = [
            us.to_dict(include_relationships=False, include_sensitive=False)
            for us in user_stories
        ]
        
        response = {
            "user_stories": user_stories_data,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit,
                "has_next": skip + limit < total,
                "has_prev": skip > 0
            },
            "filters": {
                "status": status.value if status else None,
                "domain": domain,
                "search": search,
                "complexity_min": complexity_min,
                "complexity_max": complexity_max
            }
        }
        
        logger.info(
            "User stories retrieved successfully",
            count=len(user_stories),
            total=total,
            skip=skip,
            limit=limit
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list user stories", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list user stories: {str(e)}"
        )


@router.put("/{user_story_id}", response_model=Dict[str, Any])
async def update_user_story(
    user_story_id: int,
    story_data: UserStoryUpdate,
    db: AsyncSession = Depends(get_database_session),
    _rate_limit: None = Depends(rate_limit_dependency())
) -> Dict[str, Any]:
    """
    Update an existing user story.
    
    Args:
        user_story_id: User story ID
        story_data: Updated user story data
        db: Database session
        
    Returns:
        Dict containing updated user story details
        
    Raises:
        HTTPException: If user story not found or update fails
    """
    try:
        logger.info("Updating user story", user_story_id=user_story_id)
        
        # Get existing user story
        result = await db.execute(
            select(UserStory).where(
                UserStory.id == user_story_id,
                UserStory.is_deleted == False
            )
        )
        user_story = result.scalar_one_or_none()
        
        if not user_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User story with ID {user_story_id} not found"
            )
        
        # Update fields if provided
        updated_fields = []
        
        if story_data.title is not None:
            user_story.title = story_data.title
            updated_fields.append("title")
        
        if story_data.description is not None:
            user_story.description = story_data.description
            updated_fields.append("description")
        
        if story_data.acceptance_criteria is not None:
            user_story.acceptance_criteria = story_data.acceptance_criteria
            updated_fields.append("acceptance_criteria")
        
        if story_data.domain is not None:
            user_story.domain_classification = story_data.domain
            updated_fields.append("domain")
        
        if story_data.azure_devops_id is not None:
            # Check if new Azure DevOps ID already exists
            result = await db.execute(
                select(UserStory).where(
                    UserStory.azure_devops_id == story_data.azure_devops_id,
                    UserStory.id != user_story_id,
                    UserStory.is_deleted == False
                )
            )
            existing_story = result.scalar_one_or_none()
            
            if existing_story:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User story with Azure DevOps ID '{story_data.azure_devops_id}' already exists"
                )
            
            user_story.azure_devops_id = story_data.azure_devops_id
            updated_fields.append("azure_devops_id")
        
        if not updated_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update"
            )
        
        # Set updated metadata
        user_story.updated_by = "api_user"
        
        # Validate updated content
        validation_errors = user_story.validate_content()
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed: {'; '.join(validation_errors)}"
            )
        
        # Reset processing status if content changed
        if any(field in updated_fields for field in ["title", "description", "acceptance_criteria"]):
            user_story.processing_status = ProcessingStatus.PENDING
            user_story.processed_at = None
        
        await db.commit()
        await db.refresh(user_story)
        
        # Convert to response format
        response_data = user_story.to_dict(include_relationships=False, include_sensitive=False)
        
        logger.info(
            "User story updated successfully",
            user_story_id=user_story_id,
            updated_fields=updated_fields
        )
        
        return response_data
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to update user story", user_story_id=user_story_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user story: {str(e)}"
        )


@router.delete("/{user_story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_story(
    user_story_id: int,
    permanent: bool = Query(False, description="Perform permanent delete instead of soft delete"),
    db: AsyncSession = Depends(get_database_session),
    _rate_limit: None = Depends(rate_limit_dependency())
):
    """
    Delete a user story (soft delete by default).
    
    Args:
        user_story_id: User story ID
        permanent: Whether to perform permanent delete
        db: Database session
        
    Raises:
        HTTPException: If user story not found or deletion fails
    """
    try:
        logger.info("Deleting user story", user_story_id=user_story_id, permanent=permanent)
        
        # Get existing user story
        result = await db.execute(
            select(UserStory).where(
                UserStory.id == user_story_id,
                UserStory.is_deleted == False if not permanent else True
            )
        )
        user_story = result.scalar_one_or_none()
        
        if not user_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User story with ID {user_story_id} not found"
            )
        
        if permanent:
            # Permanent delete - remove from database
            await db.delete(user_story)
            logger.info("User story permanently deleted", user_story_id=user_story_id)
        else:
            # Soft delete - mark as deleted
            user_story.soft_delete(deleted_by="api_user")
            logger.info("User story soft deleted", user_story_id=user_story_id)
        
        await db.commit()
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to delete user story", user_story_id=user_story_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user story: {str(e)}"
        )


@router.post("/{user_story_id}/restore", response_model=Dict[str, Any])
async def restore_user_story(
    user_story_id: int,
    db: AsyncSession = Depends(get_database_session),
    _rate_limit: None = Depends(rate_limit_dependency())
) -> Dict[str, Any]:
    """
    Restore a soft-deleted user story.
    
    Args:
        user_story_id: User story ID
        db: Database session
        
    Returns:
        Dict containing restored user story details
        
    Raises:
        HTTPException: If user story not found or restore fails
    """
    try:
        logger.info("Restoring user story", user_story_id=user_story_id)
        
        # Get soft-deleted user story
        result = await db.execute(
            select(UserStory).where(
                UserStory.id == user_story_id,
                UserStory.is_deleted == True
            )
        )
        user_story = result.scalar_one_or_none()
        
        if not user_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Deleted user story with ID {user_story_id} not found"
            )
        
        # Restore the user story
        user_story.restore(updated_by="api_user")
        
        await db.commit()
        await db.refresh(user_story)
        
        # Convert to response format
        response_data = user_story.to_dict(include_relationships=False, include_sensitive=False)
        
        logger.info("User story restored successfully", user_story_id=user_story_id)
        return response_data
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Failed to restore user story", user_story_id=user_story_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore user story: {str(e)}"
        )


@router.get("/{user_story_id}/statistics", response_model=Dict[str, Any])
async def get_user_story_statistics(
    user_story_id: int,
    db: AsyncSession = Depends(get_database_session)
) -> Dict[str, Any]:
    """
    Get statistics for a user story.
    
    Args:
        user_story_id: User story ID
        db: Database session
        
    Returns:
        Dict containing user story statistics
        
    Raises:
        HTTPException: If user story not found
    """
    try:
        logger.info("Getting user story statistics", user_story_id=user_story_id)
        
        # Get user story with test cases
        result = await db.execute(
            select(UserStory)
            .options(selectinload(UserStory.test_cases))
            .where(
                UserStory.id == user_story_id,
                UserStory.is_deleted == False
            )
        )
        user_story = result.scalar_one_or_none()
        
        if not user_story:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User story with ID {user_story_id} not found"
            )
        
        # Calculate statistics
        test_cases = [tc for tc in user_story.test_cases if not tc.is_deleted]
        
        statistics = {
            "user_story_id": user_story_id,
            "azure_devops_id": user_story.azure_devops_id,
            "title": user_story.title,
            "processing_status": user_story.processing_status.value,
            "complexity_score": float(user_story.complexity_score) if user_story.complexity_score else None,
            "complexity_level": user_story.complexity_level,
            "domain_classification": user_story.domain_classification,
            "test_cases": {
                "total": len(test_cases),
                "by_classification": {},
                "by_priority": {},
                "by_type": {},
                "automated": 0,
                "manual": 0
            },
            "quality_metrics": {
                "average_quality_score": 0.0,
                "high_quality_cases": 0,
                "validation_passed": 0
            },
            "timestamps": {
                "created_at": user_story.created_at.isoformat() if user_story.created_at else None,
                "updated_at": user_story.updated_at.isoformat() if user_story.updated_at else None,
                "processed_at": user_story.processed_at.isoformat() if user_story.processed_at else None,
                "days_since_created": user_story.days_since_created
            }
        }
        
        # Calculate test case statistics
        if test_cases:
            from collections import Counter
            
            # Count by classification
            classifications = [tc.classification.value for tc in test_cases if tc.classification]
            statistics["test_cases"]["by_classification"] = dict(Counter(classifications))
            
            # Count by priority
            priorities = [tc.priority.value for tc in test_cases if tc.priority]
            statistics["test_cases"]["by_priority"] = dict(Counter(priorities))
            
            # Count by test type
            types = [tc.test_type for tc in test_cases if tc.test_type]
            statistics["test_cases"]["by_type"] = dict(Counter(types))
            
            # Count automated vs manual
            for tc in test_cases:
                if tc.is_automated:
                    statistics["test_cases"]["automated"] += 1
                else:
                    statistics["test_cases"]["manual"] += 1
            
            # Calculate quality metrics
            quality_scores = []
            high_quality_count = 0
            validation_passed_count = 0
            
            for tc in test_cases:
                if tc.quality_metrics:
                    score = float(tc.quality_metrics.overall_score)
                    quality_scores.append(score)
                    
                    if score >= 0.8:
                        high_quality_count += 1
                    
                    if tc.quality_metrics.validation_passed:
                        validation_passed_count += 1
            
            if quality_scores:
                statistics["quality_metrics"]["average_quality_score"] = sum(quality_scores) / len(quality_scores)
            
            statistics["quality_metrics"]["high_quality_cases"] = high_quality_count
            statistics["quality_metrics"]["validation_passed"] = validation_passed_count
        
        logger.info("User story statistics retrieved successfully", user_story_id=user_story_id)
        return statistics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user story statistics", user_story_id=user_story_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user story statistics: {str(e)}"
        )
