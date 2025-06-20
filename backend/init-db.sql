-- Initialize the Test Generation Agent Database
-- This file is automatically executed when the PostgreSQL container starts

-- Enable required extensions for the Test Generation Agent
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Try to create vector extension, but don't fail if it doesn't exist
-- The vector extension is needed for pgvector support but may not be available in all PostgreSQL images
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS "vector" CASCADE;
    RAISE NOTICE 'Vector extension enabled successfully';
EXCEPTION WHEN others THEN
    RAISE NOTICE 'Vector extension not available - similarity search will use alternative methods';
END
$$;

-- Create application schema
CREATE SCHEMA IF NOT EXISTS testgen;

-- Set default schema for this session
SET search_path TO testgen, public;

-- Create enum types for the application
DO $ BEGIN
    CREATE TYPE processing_status AS ENUM (
        'pending',
        'processing', 
        'completed',
        'failed',
        'queued_for_review'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $;

DO $ BEGIN
    CREATE TYPE test_classification AS ENUM (
        'manual',
        'api_automation',
        'ui_automation', 
        'performance',
        'security',
        'integration'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $;

DO $ BEGIN
    CREATE TYPE confidence_level AS ENUM (
        'low',
        'medium', 
        'high'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $;

DO $ BEGIN
    CREATE TYPE quality_rating AS ENUM (
        'poor',
        'fair',
        'good',
        'excellent'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $;

-- Core tables for user stories and test cases
CREATE TABLE IF NOT EXISTS user_stories (
    id SERIAL PRIMARY KEY,
    azure_devops_id VARCHAR(100) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    original_content JSONB, -- Store original content before normalization
    normalization_metadata JSONB, -- Metadata about content normalization
    complexity_score DECIMAL(3,2) CHECK (complexity_score BETWEEN 0 AND 1),
    domain_classification VARCHAR(50),
    processing_status processing_status DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS test_cases (
    id SERIAL PRIMARY KEY,
    user_story_id INTEGER REFERENCES user_stories(id) ON DELETE CASCADE,
    azure_devops_id VARCHAR(100) UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    steps JSONB NOT NULL, -- Array of test steps with actions and expected results
    test_data JSONB, -- Test data associated with the test case
    classification test_classification,
    classification_confidence DECIMAL(3,2) CHECK (classification_confidence BETWEEN 0 AND 1),
    classification_reasoning TEXT,
    estimated_duration INTEGER, -- Estimated duration in minutes
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'system'
);

-- Quality metrics table for tracking test case quality
CREATE TABLE IF NOT EXISTS quality_metrics (
    id SERIAL PRIMARY KEY,
    test_case_id INTEGER REFERENCES test_cases(id) ON DELETE CASCADE,
    overall_score DECIMAL(3,2) NOT NULL CHECK (overall_score BETWEEN 0 AND 1),
    clarity_score DECIMAL(3,2) NOT NULL CHECK (clarity_score BETWEEN 0 AND 1),
    completeness_score DECIMAL(3,2) NOT NULL CHECK (completeness_score BETWEEN 0 AND 1),
    executability_score DECIMAL(3,2) NOT NULL CHECK (executability_score BETWEEN 0 AND 1),
    traceability_score DECIMAL(3,2) NOT NULL CHECK (traceability_score BETWEEN 0 AND 1),
    realism_score DECIMAL(3,2) NOT NULL CHECK (realism_score BETWEEN 0 AND 1),
    coverage_score DECIMAL(3,2) NOT NULL CHECK (coverage_score BETWEEN 0 AND 1),
    confidence_level confidence_level NOT NULL,
    validation_passed BOOLEAN NOT NULL DEFAULT false,
    benchmark_percentile DECIMAL(5,2),
    quality_issues JSONB, -- Array of identified quality issues
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    calculation_version VARCHAR(20) NOT NULL DEFAULT '1.0'
);

-- QA annotations table for human feedback
CREATE TABLE IF NOT EXISTS qa_annotations (
    id SERIAL PRIMARY KEY,
    test_case_id INTEGER REFERENCES test_cases(id) ON DELETE CASCADE,
    annotator_id VARCHAR(100) NOT NULL,
    overall_quality_rating INTEGER CHECK (overall_quality_rating BETWEEN 1 AND 5),
    quality_issues JSONB, -- Structured quality issues identified
    positive_aspects TEXT[],
    clarity_feedback TEXT,
    completeness_feedback TEXT,
    executability_feedback TEXT,
    improvement_suggestions JSONB,
    suggested_classification test_classification,
    classification_reasoning TEXT,
    execution_difficulty VARCHAR(20),
    execution_time_actual INTEGER, -- Actual execution time in minutes
    execution_issues TEXT[],
    annotation_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_processed BOOLEAN DEFAULT false,
    processing_timestamp TIMESTAMP WITH TIME ZONE
);

-- Learning contributions table for tracking AI improvements
CREATE TABLE IF NOT EXISTS learning_contributions (
    id SERIAL PRIMARY KEY,
    test_case_id INTEGER REFERENCES test_cases(id) ON DELETE CASCADE,
    annotation_id INTEGER REFERENCES qa_annotations(id) ON DELETE SET NULL,
    contribution_type VARCHAR(50) NOT NULL,
    pattern_identified JSONB,
    improvement_applied TEXT,
    quality_impact DECIMAL(3,2),
    prompt_updates JSONB,
    model_training_data JSONB,
    validation_rule_updates JSONB,
    contribution_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    applied_timestamp TIMESTAMP WITH TIME ZONE,
    effectiveness_score DECIMAL(3,2)
);

-- Ground truth benchmark table for quality measurement
CREATE TABLE IF NOT EXISTS ground_truth_benchmark (
    id SERIAL PRIMARY KEY,
    user_story_id INTEGER REFERENCES user_stories(id) ON DELETE CASCADE,
    benchmark_story_content JSONB NOT NULL,
    expert_test_cases JSONB NOT NULL,
    domain VARCHAR(50) NOT NULL,
    complexity_level VARCHAR(20) NOT NULL,
    reviewer_id VARCHAR(100) NOT NULL,
    reviewer_experience_level VARCHAR(20) NOT NULL,
    quality_rating DECIMAL(3,2) NOT NULL CHECK (quality_rating BETWEEN 0 AND 1),
    coverage_completeness DECIMAL(3,2) NOT NULL CHECK (coverage_completeness BETWEEN 0 AND 1),
    benchmark_creation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_validation_date TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    usage_count INTEGER DEFAULT 0
);

-- System health and monitoring tables
CREATE TABLE IF NOT EXISTS system_health_log (
    id SERIAL PRIMARY KEY,
    component VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    metrics JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Generation statistics table
CREATE TABLE IF NOT EXISTS generation_statistics (
    id SERIAL PRIMARY KEY,
    user_story_id INTEGER REFERENCES user_stories(id) ON DELETE CASCADE,
    generation_start TIMESTAMP WITH TIME ZONE NOT NULL,
    generation_end TIMESTAMP WITH TIME ZONE,
    test_cases_generated INTEGER DEFAULT 0,
    test_cases_passed_validation INTEGER DEFAULT 0,
    average_quality_score DECIMAL(3,2),
    processing_time_seconds INTEGER,
    tokens_used INTEGER,
    generation_parameters JSONB,
    errors JSONB
);

-- Create indexes for performance optimization
-- User stories indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_stories_azure_devops_id 
ON user_stories (azure_devops_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_stories_status_created 
ON user_stories (processing_status, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_stories_domain_complexity 
ON user_stories (domain_classification, complexity_score DESC NULLS LAST);

-- Test cases indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_test_cases_user_story 
ON test_cases (user_story_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_test_cases_classification 
ON test_cases (classification, classification_confidence DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_test_cases_azure_devops_id 
ON test_cases (azure_devops_id) WHERE azure_devops_id IS NOT NULL;

-- Quality metrics indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quality_metrics_overall_score 
ON quality_metrics (overall_score DESC, calculated_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quality_metrics_test_case 
ON quality_metrics (test_case_id, calculated_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quality_metrics_validation 
ON quality_metrics (validation_passed, confidence_level, overall_score DESC);

-- QA annotations indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_annotations_test_case 
ON qa_annotations (test_case_id, annotation_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_annotations_quality_rating 
ON qa_annotations (overall_quality_rating, annotation_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_annotations_processing 
ON qa_annotations (is_processed, annotation_timestamp) WHERE NOT is_processed;

-- Learning contributions indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_learning_contributions_type_impact 
ON learning_contributions (contribution_type, quality_impact DESC NULLS LAST);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_learning_contributions_timestamp 
ON learning_contributions (contribution_timestamp DESC);

-- Benchmark indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_benchmark_domain_complexity 
ON ground_truth_benchmark (domain, complexity_level, quality_rating DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_benchmark_active_usage 
ON ground_truth_benchmark (is_active, usage_count DESC) WHERE is_active = true;

-- System health indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_health_component_timestamp 
ON system_health_log (component, timestamp DESC);

-- Generation statistics indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_generation_stats_user_story 
ON generation_statistics (user_story_id, generation_start DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_generation_stats_performance 
ON generation_statistics (generation_start DESC, processing_time_seconds, average_quality_score DESC);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_user_stories_updated_at 
    BEFORE UPDATE ON user_stories 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_test_cases_updated_at 
    BEFORE UPDATE ON test_cases 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions to the application user
GRANT ALL PRIVILEGES ON SCHEMA testgen TO testgen_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA testgen TO testgen_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA testgen TO testgen_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA testgen TO testgen_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA testgen GRANT ALL ON TABLES TO testgen_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA testgen GRANT ALL ON SEQUENCES TO testgen_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA testgen GRANT EXECUTE ON FUNCTIONS TO testgen_user;

-- Insert initial system health record
INSERT INTO system_health_log (component, status, message) 
VALUES ('database', 'healthy', 'Database initialized successfully')
ON CONFLICT DO NOTHING;

-- Create a view for test case quality summary
CREATE OR REPLACE VIEW test_case_quality_summary AS
SELECT 
    tc.id,
    tc.title,
    tc.classification,
    tc.classification_confidence,
    qm.overall_score,
    qm.confidence_level,
    qm.validation_passed,
    qm.benchmark_percentile,
    us.domain_classification,
    us.complexity_score,
    COUNT(qa.id) as annotation_count,
    AVG(qa.overall_quality_rating) as avg_human_rating,
    tc.created_at
FROM test_cases tc
LEFT JOIN quality_metrics qm ON tc.id = qm.test_case_id
LEFT JOIN user_stories us ON tc.user_story_id = us.id
LEFT JOIN qa_annotations qa ON tc.id = qa.test_case_id
GROUP BY tc.id, tc.title, tc.classification, tc.classification_confidence, 
         qm.overall_score, qm.confidence_level, qm.validation_passed, qm.benchmark_percentile,
         us.domain_classification, us.complexity_score, tc.created_at;

-- Grant access to the view
GRANT SELECT ON test_case_quality_summary TO testgen_user;

-- Log successful initialization
INSERT INTO system_health_log (component, status, message, metrics) 
VALUES (
    'database_init', 
    'completed', 
    'Database schema and tables created successfully',
    jsonb_build_object(
        'schema_created', true,
        'tables_created', (
            SELECT count(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'testgen'
        ),
        'indexes_created', true,
        'permissions_granted', true
    )
);

-- Final message
SELECT 'Test Generation Agent database initialized successfully!' as status;
