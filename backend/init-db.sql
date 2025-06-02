-- Initialize the database with required extensions and schemas
-- This file is automatically executed when the PostgreSQL container starts

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector" CASCADE;

-- Create application schema
CREATE SCHEMA IF NOT EXISTS testgen;

-- Set default schema
SET search_path TO testgen, public;

-- Create initial tables will be handled by Alembic migrations
-- This is just for basic setup and extensions

-- Grant permissions to the application user
GRANT ALL PRIVILEGES ON SCHEMA testgen TO testgen_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA testgen TO testgen_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA testgen TO testgen_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA testgen GRANT ALL ON TABLES TO testgen_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA testgen GRANT ALL ON SEQUENCES TO testgen_user;
