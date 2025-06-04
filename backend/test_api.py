#!/usr/bin/env python3
"""
Test script for the Test Generation Agent API endpoints.

This script tests all the basic API endpoints to ensure they are working correctly.
"""

import asyncio
import aiohttp
import json
import sys
from typing import Dict, Any


BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"


async def test_health_endpoint():
    """Test the health check endpoint."""
    print("Testing health endpoint...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/health") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Health check passed: {data}")
                return True
            else:
                print(f"❌ Health check failed: {response.status}")
                return False


async def test_create_user_story():
    """Test creating a user story."""
    print("\nTesting user story creation...")
    
    user_story_data = {
        "title": "As a user, I want to login to the application so that I can access my account",
        "description": "The user should be able to login using email and password to access their personal account dashboard.",
        "acceptance_criteria": "Given I am on the login page\nWhen I enter valid credentials\nThen I should be redirected to my dashboard",
        "domain": "saas",
        "azure_devops_id": "test-story-001"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE}/user-stories",
            json=user_story_data,
            headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 201:
                data = await response.json()
                print(f"✅ User story created: ID {data['id']}")
                return data["id"]
            else:
                error_text = await response.text()
                print(f"❌ User story creation failed: {response.status} - {error_text}")
                return None


async def test_get_user_story(user_story_id: int):
    """Test retrieving a user story."""
    print(f"\nTesting user story retrieval for ID {user_story_id}...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/user-stories/{user_story_id}") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ User story retrieved: {data['title']}")
                return True
            else:
                error_text = await response.text()
                print(f"❌ User story retrieval failed: {response.status} - {error_text}")
                return False


async def test_list_user_stories():
    """Test listing user stories."""
    print("\nTesting user stories listing...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/user-stories?limit=10") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ User stories listed: {len(data['user_stories'])} stories found")
                return True
            else:
                error_text = await response.text()
                print(f"❌ User stories listing failed: {response.status} - {error_text}")
                return False


async def test_generate_test_cases():
    """Test test case generation."""
    print("\nTesting test case generation...")
    
    generation_request = {
        "story": {
            "title": "As a user, I want to add items to my shopping cart so that I can purchase them later",
            "description": "Users should be able to add products to their shopping cart from the product catalog. The cart should maintain items across sessions and allow quantity adjustments.",
            "acceptance_criteria": "Given I am viewing a product\nWhen I click 'Add to Cart'\nThen the item should appear in my cart\nAnd the cart counter should update\nAnd I should see a confirmation message",
            "domain": "ecommerce"
        },
        "options": {
            "include_personas": False,
            "include_performance": False,
            "quality_threshold": 0.7,
            "max_test_cases": 5
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE}/test-cases/generate",
            json=generation_request,
            headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Test cases generated: {len(data['test_cases'])} cases")
                print(f"   Average quality score: {data['summary']['average_quality_score']:.2f}")
                return data["test_cases"]
            else:
                error_text = await response.text()
                print(f"❌ Test case generation failed: {response.status} - {error_text}")
                return None


async def test_list_test_cases():
    """Test listing test cases."""
    print("\nTesting test cases listing...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/test-cases?limit=10") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Test cases listed: {len(data['test_cases'])} cases found")
                return True
            else:
                error_text = await response.text()
                print(f"❌ Test cases listing failed: {response.status} - {error_text}")
                return False


async def test_update_user_story(user_story_id: int):
    """Test updating a user story."""
    print(f"\nTesting user story update for ID {user_story_id}...")
    
    update_data = {
        "description": "Updated description: The user should be able to login using email and password to access their personal account dashboard with enhanced security features."
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.put(
            f"{API_BASE}/user-stories/{user_story_id}",
            json=update_data,
            headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ User story updated successfully")
                return True
            else:
                error_text = await response.text()
                print(f"❌ User story update failed: {response.status} - {error_text}")
                return False


async def test_user_story_statistics(user_story_id: int):
    """Test getting user story statistics."""
    print(f"\nTesting user story statistics for ID {user_story_id}...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/user-stories/{user_story_id}/statistics") as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ User story statistics retrieved: {data['test_cases']['total']} test cases")
                return True
            else:
                error_text = await response.text()
                print(f"❌ User story statistics failed: {response.status} - {error_text}")
                return False


async def test_api_documentation():
    """Test API documentation endpoints."""
    print("\nTesting API documentation...")
    
    async with aiohttp.ClientSession() as session:
        # Test OpenAPI schema
        async with session.get(f"{API_BASE}/openapi.json") as response:
            if response.status == 200:
                print("✅ OpenAPI schema accessible")
            else:
                print(f"❌ OpenAPI schema failed: {response.status}")
        
        # Test Swagger UI
        async with session.get(f"{API_BASE}/docs") as response:
            if response.status == 200:
                print("✅ Swagger UI accessible")
            else:
                print(f"❌ Swagger UI failed: {response.status}")


async def main():
    """Run all API tests."""
    print("🚀 Starting Test Generation Agent API Tests\n")
    
    results = []
    
    # Test health endpoint
    results.append(await test_health_endpoint())
    
    # Test user story CRUD operations
    user_story_id = await test_create_user_story()
    if user_story_id:
        results.append(await test_get_user_story(user_story_id))
        results.append(await test_update_user_story(user_story_id))
        results.append(await test_user_story_statistics(user_story_id))
    
    # Test user story listing
    results.append(await test_list_user_stories())
    
    # Test test case generation
    test_cases = await test_generate_test_cases()
    if test_cases:
        results.append(True)
    else:
        results.append(False)
    
    # Test test case listing
    results.append(await test_list_test_cases())
    
    # Test API documentation
    await test_api_documentation()
    
    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! API endpoints are working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
