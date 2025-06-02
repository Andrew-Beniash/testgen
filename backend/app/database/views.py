"""
Database views for common queries in the Test Generation Agent.

This file contains SQL view definitions that provide optimized access
to commonly queried data combinations.
"""

# SQL for creating database views

CREATE_VIEWS_SQL = """
-- Set schema for views
SET search_path TO testgen, public;

-- Drop existing views if they exist
DROP VIEW IF EXISTS test_case_quality_summary CASCADE;
DROP VIEW IF EXISTS user_story_processing_status CASCADE;
DROP VIEW IF EXISTS qa_feedback_summary CASCADE;
DROP VIEW IF EXISTS generation_performance_summary CASCADE;
DROP VIEW IF EXISTS benchmark_usage_summary CASCADE;
DROP VIEW IF EXISTS system_health_dashboard CASCADE;

-- Test Case Quality Summary View
-- Provides comprehensive quality information for test cases
CREATE VIEW test_case_quality_summary AS
SELECT 
    tc.id as test_case_id,
    tc.title,
    tc.classification,
    tc.classification_confidence,
    tc.estimated_duration,
    tc.created_at,
    tc.created_by,
    
    -- User story information
    us.id as user_story_id,
    us.azure_devops_id as story_azure_id,
    us.title as story_title,
    us.domain_classification,
    us.complexity_score,
    us.processing_status,
    
    -- Quality metrics
    qm.overall_score,
    qm.clarity_score,
    qm.completeness_score,
    qm.executability_score,
    qm.traceability_score,
    qm.realism_score,
    qm.coverage_score,
    qm.confidence_level,
    qm.validation_passed,
    qm.benchmark_percentile,
    qm.calculated_at as quality_calculated_at,
    
    -- QA feedback aggregation
    COUNT(qa.id) as annotation_count,
    AVG(qa.overall_quality_rating) as avg_human_rating,
    COUNT(CASE WHEN qa.overall_quality_rating >= 4 THEN 1 END) as positive_ratings,
    COUNT(CASE WHEN qa.overall_quality_rating <= 2 THEN 1 END) as negative_ratings,
    
    -- Learning contributions
    COUNT(lc.id) as learning_contributions_count,
    AVG(lc.quality_impact) as avg_learning_impact,
    
    -- Classification accuracy indicator
    CASE 
        WHEN COUNT(qa.suggested_classification) > 0 THEN
            COUNT(CASE WHEN qa.suggested_classification = tc.classification::text THEN 1 END)::float / 
            COUNT(qa.suggested_classification)
        ELSE NULL
    END as classification_accuracy,
    
    -- Quality trend indicator
    CASE 
        WHEN qm.overall_score >= 0.9 THEN 'excellent'
        WHEN qm.overall_score >= 0.8 THEN 'good'
        WHEN qm.overall_score >= 0.7 THEN 'fair'
        WHEN qm.overall_score >= 0.6 THEN 'poor'
        ELSE 'very_poor'
    END as quality_grade

FROM test_cases tc
LEFT JOIN user_stories us ON tc.user_story_id = us.id
LEFT JOIN quality_metrics qm ON tc.id = qm.test_case_id
LEFT JOIN qa_annotations qa ON tc.id = qa.test_case_id
LEFT JOIN learning_contributions lc ON tc.id = lc.test_case_id
GROUP BY tc.id, tc.title, tc.classification, tc.classification_confidence, 
         tc.estimated_duration, tc.created_at, tc.created_by,
         us.id, us.azure_devops_id, us.title, us.domain_classification, 
         us.complexity_score, us.processing_status,
         qm.overall_score, qm.clarity_score, qm.completeness_score,
         qm.executability_score, qm.traceability_score, qm.realism_score,
         qm.coverage_score, qm.confidence_level, qm.validation_passed,
         qm.benchmark_percentile, qm.calculated_at;

-- User Story Processing Status View
-- Provides processing status and progress information for user stories
CREATE VIEW user_story_processing_status AS
SELECT 
    us.id,
    us.azure_devops_id,
    us.title,
    us.description,
    us.domain_classification,
    us.complexity_score,
    us.processing_status,
    us.created_at,
    us.updated_at,
    us.processed_at,
    
    -- Test case generation summary
    COUNT(tc.id) as test_cases_generated,
    COUNT(CASE WHEN qm.validation_passed = true THEN 1 END) as test_cases_passed_validation,
    AVG(qm.overall_score) as avg_quality_score,
    
    -- Generation statistics
    gs.generation_start,
    gs.generation_end,
    gs.processing_time_seconds,
    gs.tokens_used,
    
    -- QA feedback summary
    COUNT(qa.id) as total_annotations,
    AVG(qa.overall_quality_rating) as avg_qa_rating,
    
    -- Processing efficiency metrics
    CASE 
        WHEN us.processing_status = 'completed' AND COUNT(tc.id) > 0 THEN 'successful'
        WHEN us.processing_status = 'completed' AND COUNT(tc.id) = 0 THEN 'no_output'
        WHEN us.processing_status = 'failed' THEN 'failed'
        WHEN us.processing_status = 'processing' THEN 'in_progress'
        ELSE 'pending'
    END as processing_outcome,
    
    -- Time since creation
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - us.created_at))/3600 as hours_since_creation,
    
    -- Benchmark comparison
    COUNT(gtb.id) as benchmark_entries

FROM user_stories us
LEFT JOIN test_cases tc ON us.id = tc.user_story_id
LEFT JOIN quality_metrics qm ON tc.id = qm.test_case_id
LEFT JOIN qa_annotations qa ON tc.id = qa.test_case_id
LEFT JOIN generation_statistics gs ON us.id = gs.user_story_id
LEFT JOIN ground_truth_benchmark gtb ON us.id = gtb.user_story_id
GROUP BY us.id, us.azure_devops_id, us.title, us.description, 
         us.domain_classification, us.complexity_score, us.processing_status,
         us.created_at, us.updated_at, us.processed_at,
         gs.generation_start, gs.generation_end, gs.processing_time_seconds,
         gs.tokens_used;

-- Grant permissions on views
GRANT SELECT ON test_case_quality_summary TO testgen_user;
GRANT SELECT ON user_story_processing_status TO testgen_user;

-- Log successful view creation
INSERT INTO system_health_log (component, status, message, metrics) 
VALUES (
    'database_views', 
    'healthy', 
    'Core database views created successfully',
    jsonb_build_object(
        'views_created', 2,
        'permissions_granted', true
    )
);
"""

# Python function to execute view creation
def create_database_views(connection):
    """
    Create database views for common queries.
    
    Args:
        connection: Database connection object
    """
    try:
        # Execute the view creation SQL
        connection.execute(CREATE_VIEWS_SQL)
        connection.commit()
        
        print("Database views created successfully")
        return True
        
    except Exception as e:
        print(f"Error creating database views: {e}")
        connection.rollback()
        return False


# Common query patterns for the views
COMMON_QUERIES = {
    "high_quality_test_cases": """
        SELECT * FROM testgen.test_case_quality_summary 
        WHERE overall_score >= 0.8 AND validation_passed = true
        ORDER BY overall_score DESC, created_at DESC
    """,
    
    "pending_user_stories": """
        SELECT * FROM testgen.user_story_processing_status 
        WHERE processing_status IN ('pending', 'processing')
        ORDER BY hours_since_creation DESC
    """,
    
    "quality_summary_by_domain": """
        SELECT 
            domain_classification,
            COUNT(*) as total_test_cases,
            AVG(overall_score) as avg_quality_score,
            COUNT(CASE WHEN validation_passed = true THEN 1 END) as passed_validation,
            COUNT(CASE WHEN overall_score >= 0.8 THEN 1 END) as high_quality_cases
        FROM testgen.test_case_quality_summary 
        WHERE domain_classification IS NOT NULL
        GROUP BY domain_classification
        ORDER BY avg_quality_score DESC
    """,
    
    "recent_processing_activity": """
        SELECT * FROM testgen.user_story_processing_status 
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY created_at DESC
    """,
    
    "test_cases_needing_review": """
        SELECT * FROM testgen.test_case_quality_summary 
        WHERE overall_score < 0.75 
           OR annotation_count = 0 
           OR negative_ratings > positive_ratings
        ORDER BY overall_score ASC, created_at DESC
    """
}
