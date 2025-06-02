# Database Setup - Test Generation Agent

This document describes the database setup and management for the Test Generation Agent v2.0.

## Overview

The system uses PostgreSQL as the primary database with the following components:

- **PostgreSQL 15**: Primary database with persistent volumes
- **Test Database**: Separate database for testing
- **Connection Pooling**: SQLAlchemy async engine with connection pooling
- **Health Monitoring**: Comprehensive health checks and monitoring
- **Quality Tables**: Enhanced schema for quality assurance features

## Quick Start

### 1. Start the Database Services

```bash
# Start all services
docker-compose up -d

# Start with development overrides (includes pgAdmin)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Start only database services
docker-compose up -d postgres redis qdrant
```

### 2. Verify Database Setup

```bash
# Using the database manager script
python scripts/db_manager.py health

# Or check via API (once backend is running)
curl http://localhost:8000/health/database
```

### 3. Initialize Database (if needed)

```bash
# Initialize with tables and initial data
python scripts/db_manager.py init

# Or reset everything
python scripts/db_manager.py reset
```

## Database Configuration

### Connection Settings

The database connection is configured via environment variables:

```env
DATABASE_URL="postgresql+asyncpg://testgen_user:testgen_password@localhost:5432/testgen_db"
DATABASE_TEST_URL="postgresql+asyncpg://testgen_test_user:testgen_test_password@localhost:5433/testgen_test_db"
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_ECHO=false
DATABASE_TIMEOUT=30
DATABASE_RETRY_ATTEMPTS=3
```

### Connection Pool

The system uses SQLAlchemy's async connection pooling with:

- **Pool Size**: 20 connections
- **Max Overflow**: 30 additional connections
- **Pool Pre-ping**: Validates connections before use
- **Pool Recycle**: Recycles connections every hour

## Database Schema

### Core Tables

1. **user_stories**: User stories from Azure DevOps
2. **test_cases**: Generated test cases with quality metrics
3. **quality_metrics**: Quality scores and validation results
4. **qa_annotations**: Human feedback and annotations
5. **learning_contributions**: AI learning and improvement data
6. **ground_truth_benchmark**: Expert test cases for quality measurement
7. **system_health_log**: System health and monitoring data
8. **generation_statistics**: Test generation performance metrics

### Enhanced Features

- **Quality Scoring**: Multi-dimensional quality metrics
- **Learning System**: Continuous improvement from feedback
- **Benchmark Comparison**: Quality measurement against expert standards
- **Health Monitoring**: Comprehensive system health tracking

## Management Scripts

### Database Manager

The `scripts/db_manager.py` script provides comprehensive database management:

```bash
# Available commands
python scripts/db_manager.py --help

# Common operations
python scripts/db_manager.py init          # Initialize database
python scripts/db_manager.py health        # Check health
python scripts/db_manager.py info          # Show configuration
python scripts/db_manager.py reset         # Reset database
python scripts/db_manager.py cleanup-logs  # Clean old logs

# Test database operations
python scripts/db_manager.py test-setup    # Setup test database
python scripts/db_manager.py test-cleanup  # Clean test data
python scripts/db_manager.py test-drop     # Drop test tables
```

## Health Monitoring

### Health Check Endpoints

- `GET /health`: Basic health check
- `GET /health/detailed`: Comprehensive diagnostics
- `GET /health/database`: Database-specific health
- `GET /health/components`: All system components
- `GET /health/readiness`: Kubernetes readiness probe
- `GET /health/liveness`: Kubernetes liveness probe
- `GET /metrics`: Prometheus-compatible metrics

### Health Check Features

- **Connection Testing**: Validates database connectivity
- **Performance Metrics**: Connection pool, query performance
- **Schema Validation**: Ensures all required tables exist
- **Error Tracking**: Monitors error rates and patterns
- **Automated Cleanup**: Removes old health logs

## Testing

### Test Database

A separate test database is configured for running tests:

```bash
# Setup test database
python scripts/db_manager.py test-setup

# Run tests
pytest tests/test_database.py -v

# Clean up after tests
python scripts/db_manager.py test-cleanup
```

### Test Features

- **Isolated Testing**: Separate test database
- **Data Factories**: Pre-built test data generators
- **Cleanup Automation**: Automatic cleanup after tests
- **Performance Testing**: Query performance measurement

## Development Tools

### pgAdmin (Optional)

When using the development Docker Compose override, pgAdmin is available:

```bash
# Start with development tools
docker-compose -f docker-compose.yml -f docker-compose.dev.yml --profile tools up -d

# Access pgAdmin at http://localhost:5050
# Email: admin@testgen.com
# Password: admin
```

### Database Access

Direct database access for development:

```bash
# Connect to main database
docker exec -it testgen_postgres psql -U testgen_user -d testgen_db

# Connect to test database
docker exec -it testgen_postgres_test psql -U testgen_test_user -d testgen_test_db

# Run SQL files
docker exec -i testgen_postgres psql -U testgen_user -d testgen_db < init-db.sql
```

## Performance Optimization

### Indexes

The database includes optimized indexes for:

- User story processing status and timestamps
- Test case quality scores and classifications
- QA annotation processing queues
- Benchmark similarity searches
- Health log monitoring

### Query Optimization

- **Connection Pooling**: Reduces connection overhead
- **Prepared Statements**: Improves query performance
- **Async Operations**: Non-blocking database operations
- **Batch Processing**: Efficient bulk operations

## Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   # Check if PostgreSQL is running
   docker-compose ps postgres
   
   # Check logs
   docker-compose logs postgres
   ```

2. **Permission Denied**
   ```bash
   # Ensure data directory permissions
   sudo chown -R 999:999 ./data/postgres
   ```

3. **Health Check Failures**
   ```bash
   # Check detailed health status
   python scripts/db_manager.py health
   
   # Check application logs
   docker-compose logs backend
   ```

### Log Locations

- **PostgreSQL Logs**: `./logs/postgres/`
- **Application Logs**: `./logs/`
- **Health Logs**: Stored in `system_health_log` table

## Security

### Database Security

- **User Isolation**: Separate database users for main and test
- **Connection Encryption**: TLS connections in production
- **Password Security**: Environment variable configuration
- **Access Control**: Role-based database permissions

### Network Security

- **Container Network**: Isolated Docker network
- **Port Exposure**: Only necessary ports exposed
- **Health Checks**: Continuous monitoring

## Backup and Recovery

### Automated Backups

```bash
# Manual backup
docker exec testgen_postgres pg_dump -U testgen_user testgen_db > backup.sql

# Restore from backup
docker exec -i testgen_postgres psql -U testgen_user -d testgen_db < backup.sql
```

### Data Persistence

- **Named Volumes**: Persistent data storage
- **Local Binding**: Development data persistence
- **Backup Strategies**: Regular backup scheduling recommended

## Migration and Scaling

### Schema Migrations

The system supports schema evolution through:

- **Database Versioning**: Track schema changes
- **Migration Scripts**: Automated schema updates
- **Rollback Support**: Safe migration rollbacks

### Scaling Considerations

- **Connection Pooling**: Handles high concurrency
- **Read Replicas**: Can be added for read scaling
- **Sharding**: Future consideration for large datasets
- **Monitoring**: Performance metrics for scaling decisions

For more information, see the main [README.md](../README.md) and [Technical Architecture Specification](../Test%20Generation%20Agent%20v2.txt).
