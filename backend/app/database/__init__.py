"""
Database package for the Test Generation Agent.

This package contains database-related functionality including
views, utilities, and database management functions.
"""

from .views import create_database_views, COMMON_QUERIES

__all__ = [
    "create_database_views",
    "COMMON_QUERIES"
]
