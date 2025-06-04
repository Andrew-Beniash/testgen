# Test Generation Agent - Basic API Endpoints

This document describes the basic API endpoints implemented for the Test Generation Agent v2.0.

## Overview

The API provides endpoints for managing user stories and generating test cases with quality assurance features. All endpoints are available under the `/api/v1` prefix.

## Authentication

Currently, the API uses basic rate limiting. In production, proper authentication will be implemented using Azure AD OAuth 2.0.

## Base URL

```
http://localhost:8000/api/v1
```

## API Documentation

- **Swagger UI**: `http://localhost:8000/api/v1/docs`
- **ReDoc**: `http://localhost:8000/api/v1/redoc`
- **OpenAPI Schema**: `http://localhost:8000/api/v1/openapi.json`

## Endpoints

### Health Check

#### GET /health
Basic health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "Test Generation Agent",
  "version": "2.0.0",
  "database": "healthy",
  "message": "Service is operational"
}
```

### User Stories

#### POST /api/v1/user-stories
Create a new user story.

**Request Body:**
```json
{
  "title": "As a user, I want to login so that I can access my account",
  "description": "Detailed description of the functionality",
  "acceptance_criteria": "Given...When...Then... format criteria",
  "domain": "saas",
  "azure_devops_id": "optional-devops-id"
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "azure_devops_id": "optional-devops-id",
  "title": "As a user, I want to login so that I can access my account",
  "description": "Detailed description of the functionality",
  "acceptance_criteria": "Given...When...Then... format criteria",
  "domain_classification": "saas",
  "processing_status": "pending",
  "complexity_level": "unknown",
  "is_processed": false,
  "needs_processing": true,
  "is_active": true,
  "total_test_cases": 0,
  "days_since_created": 0,
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### GET /api/v1/user-stories/{id}
Get a specific user story by ID.

**Query Parameters:**
- `include_test_cases` (boolean): Include associated test cases
- `include_relationships` (boolean): Include all related objects

**Response:** `200 OK`
```json
{
  "id": 1,
  "title": "User story title",
  ...
}
```

#### GET /api/v1/user-stories
List user stories with filtering and pagination.

**Query Parameters:**
- `skip` (integer): Number of records to skip (default: 0)
- `limit` (integer): Number of records to return (default: 100, max: 1000)
- `status` (string): Filter by processing status (pending, processing, completed, failed, queued_for_review)
- `domain` (string): Filter by domain classification
- `search` (string): Search in title, description, and acceptance criteria
- `complexity_min` (float): Minimum complexity score (0.0-1.0)
- `complexity_max` (float): Maximum complexity score (0.0-1.0)
- `include_test_cases` (boolean): Include test case counts

**Response:** `200 OK`
```json
{
  "user_stories": [...],
  "pagination": {
    "skip": 0,
    "limit": 100,
    "total": 150,
    "pages": 2,
    "has_next": true,
    "has_prev": false
  },
  "filters": {
    "status": null,
    "domain": null,
    "search": null
  }
}
```

#### PUT /api/v1/user-stories/{id}
Update an existing user story.

**Request Body:**
```json
{
  "title": "Updated title",
  "description": "Updated description",
  "acceptance_criteria": "Updated criteria",
  "domain": "updated-domain"
}
```

**Response:** `200 OK` - Updated user story object

#### DELETE /api/v1/user-stories/{id}
Delete a user story (soft delete by default).

**Query Parameters:**
- `permanent` (boolean): Perform permanent delete instead of soft delete

**Response:** `204 No Content`

#### POST /api/v1/user-stories/{id}/restore
Restore a soft-deleted user story.

**Response:** `200 OK` - Restored user story object

#### GET /api/v1/user-stories/{id}/statistics
Get statistics for a user story.

**Response:** `200 OK`
```json
{
  "user_story_id": 1,
  "azure_devops_id": "story-001",
  "title": "Story title",
  "processing_status": "completed",
  "complexity_score": 0.6,
  "complexity_level": "medium",
  "domain_classification": "ecommerce",
  "test_cases": {
    "total": 5,
    "by_classification": {
      "ui_automation": 3,
      "api_automation": 1,
      "manual": 1
    },
    "by_priority": {
      "high": 2,
      "medium": 2,
      "low": 1
    },
    "automated": 4,
    "manual": 1
  },
  "quality_metrics": {
    "average_quality_score": 0.85,
    "high_quality_cases": 4,
    "validation_passed": 5
  }
}
```

### Test Cases

#### POST /api/v1/test-cases/generate
Generate test cases from a user story.

**Request Body:**
```json
{
  "story": {
    "title": "As a user, I want to add items to my cart so that I can purchase them",
    "description": "Detailed functionality description",
    "acceptance_criteria": "Given...When...Then... criteria",
    "domain": "ecommerce",
    "azure_devops_id": "optional-id"
  },
  "options": {
    "include_personas": false,
    "include_performance": false,
    "quality_threshold": 0.75,
    "max_test_cases": 15,
    "test_types": ["positive", "negative", "edge"],
    "complexity_level": "medium"
  },
  "metadata": {
    "custom_field": "custom_value"
  }
}
```

**Response:** `200 OK`
```json
{
  "test_cases": [
    {
      "id": "uuid",
      "title": "Verify user can add item to cart",
      "description": "Test adding item to shopping cart",
      "steps": [
        {
          "step_number": 1,
          "action": "Navigate to product page",
          "expected_result": "Product page loads successfully",
          "test_data": {}
        }
      ],
      "test_type": "positive",
      "classification": "ui_automation",
      "classification_confidence": 0.85,
      "classification_reasoning": "Clear UI interaction points",
      "priority": "high",
      "estimated_duration": 15,
      "tags": ["smoke", "regression"],
      "quality_metrics": {
        "overall_score": 0.87,
        "clarity_score": 0.90,
        "completeness_score": 0.85,
        "executability_score": 0.88,
        "traceability_score": 0.92,
        "realism_score": 0.85,
        "coverage_score": 0.82,
        "confidence_level": "high",
        "quality_issues_count": 0,
        "validation_passed": true
      }
    }
  ],
  "summary": {
    "average_quality_score": 0.85,
    "processing_time_seconds": 2.5,
    "quality_distribution": {
      "excellent": 3,
      "good": 2,
      "fair": 0,
      "poor": 0
    },
    "complexity_score": 0.6,
    "coverage_analysis": {
      "total_criteria": 3,
      "covered_criteria": 3,
      "coverage_percentage": 100.0
    },
    "validation_summary": {
      "total_cases": 5,
      "passed_validation": 5,
      "failed_validation": 0,
      "auto_fixed": 0
    }
  },
  "generated_at": "2024-01-01T00:00:00",
  "metadata": {}
}
```

#### GET /api/v1/test-cases/{id}
Get a specific test case by ID.

**Query Parameters:**
- `include_quality` (boolean): Include quality metrics (default: true)
- `include_relationships` (boolean): Include related objects

**Response:** `200 OK` - Test case object with details

#### GET /api/v1/test-cases
List test cases with filtering and pagination.

**Query Parameters:**
- `skip` (integer): Number of records to skip
- `limit` (integer): Number of records to return
- `user_story_id` (integer): Filter by user story ID
- `classification` (string): Filter by classification type
- `priority` (string): Filter by priority level
- `tag` (string): Filter by tag
- `search` (string): Search in title and description
- `include_quality` (boolean): Include quality metrics

**Response:** `200 OK` - Paginated list of test cases

## Error Responses

### Validation Error (422)
```json
{
  "detail": "Request validation failed",
  "errors": [
    {
      "loc": ["body", "title"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ],
  "request_id": "uuid"
}
```

### Not Found (404)
```json
{
  "detail": "User story with ID 999 not found"
}
```

### Conflict (409)
```json
{
  "detail": "User story with Azure DevOps ID 'existing-id' already exists"
}
```

### Rate Limit (429)
```json
{
  "detail": "Rate limit exceeded. Too many requests per minute."
}
```

### Server Error (500)
```json
{
  "detail": "Internal server error",
  "request_id": "uuid"
}
```

## Testing

Run the API test script to verify all endpoints:

```bash
cd backend
python test_api.py
```

This will test all implemented endpoints and verify they're working correctly.

## Development

To start the development server:

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with automatic reloading enabled.
