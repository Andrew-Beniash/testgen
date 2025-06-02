"""
Test database setup and connectivity.

This module contains basic tests to verify that the database
setup is working correctly.
"""

import pytest
import asyncio
from sqlalchemy.sql import text

from app.core.database_test import (
    get_test_db_session,
    create_test_database,
    drop_test_database,
    cleanup_test_database,
    verify_test_database_setup,
    TestDataFactory
)
from app.utils.database_health import quick_health_check, detailed_health_check


class TestDatabaseSetup:
    """Test database setup and configuration."""
    
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Test basic database connectivity."""
        # This should work if the main database is running
        is_healthy = await quick_health_check()
        assert is_healthy, "Database should be healthy and connectable"
    
    @pytest.mark.asyncio
    async def test_test_database_setup(self):
        """Test that test database can be set up and torn down."""
        try:
            # Create test database
            await create_test_database()
            
            # Verify setup
            is_ready = await verify_test_database_setup()
            assert is_ready, "Test database should be properly set up"
            
            # Test basic operations
            async with get_test_db_session() as session:
                result = await session.execute(text("SELECT 1 as test"))
                assert result.scalar() == 1, "Basic query should work"
                
        finally:
            # Clean up
            await drop_test_database()
    
    @pytest.mark.asyncio
    async def test_test_data_insertion(self):
        """Test inserting and querying test data."""
        try:
            await create_test_database()
            
            async with get_test_db_session() as session:
                # Insert test user story
                story_data = TestDataFactory.create_user_story_data(
                    azure_devops_id="TEST-123",
                    title="Test story for database test"
                )
                
                # Insert user story
                insert_query = text("""
                    INSERT INTO testgen.user_stories 
                    (azure_devops_id, title, description, acceptance_criteria, complexity_score, domain_classification)
                    VALUES (:azure_devops_id, :title, :description, :acceptance_criteria, :complexity_score, :domain_classification)
                    RETURNING id
                """)
                
                result = await session.execute(insert_query, story_data)
                story_id = result.scalar()
                assert story_id is not None, "Should get a story ID back"
                
                # Query the story back
                select_query = text("SELECT title FROM testgen.user_stories WHERE id = :id")
                result = await session.execute(select_query, {"id": story_id})
                title = result.scalar()
                assert title == story_data["title"], "Should retrieve the same title"
                
        finally:
            await drop_test_database()
    
    @pytest.mark.asyncio
    async def test_health_check_functions(self):
        """Test health check functionality."""
        # Test quick health check
        is_healthy = await quick_health_check()
        assert isinstance(is_healthy, bool), "Health check should return boolean"
        
        # Test detailed health check
        health_info = await detailed_health_check()
        assert isinstance(health_info, dict), "Detailed health check should return dict"
        assert "status" in health_info, "Health info should have status"
        assert "timestamp" in health_info, "Health info should have timestamp"


class TestDatabaseHealth:
    """Test database health checking functionality."""
    
    @pytest.mark.asyncio
    async def test_detailed_health_check_structure(self):
        """Test that detailed health check returns expected structure."""
        health_info = await detailed_health_check()
        
        # Check required fields
        required_fields = ["status", "timestamp"]
        for field in required_fields:
            assert field in health_info, f"Health info should contain {field}"
        
        # Check that status is valid
        valid_statuses = ["healthy", "unhealthy"]
        assert health_info["status"] in valid_statuses, f"Status should be one of {valid_statuses}"


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
