-- Database Migration: Comprehensive Backend Improvements
-- Phase 2: Database Architecture Improvements
-- NOTE: Run this AFTER the application has created the tables via SQLAlchemy

-- =====================================================
-- 2.5 Optimize JSONB Queries with GIN Indexes
-- =====================================================

-- Enable pg_trgm extension for trigram indexing
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN index for question_data JSONB
CREATE INDEX IF NOT EXISTS idx_topic_questions_data_gin
ON topic_questions USING GIN (question_data jsonb_path_ops);

-- Index for specific JSONB queries - question text search
CREATE INDEX IF NOT EXISTS idx_topic_questions_question_text
ON topic_questions USING GIN (
    (question_data->>'text') gin_trgm_ops
);

-- Index for hash lookups within JSONB
CREATE INDEX IF NOT EXISTS idx_topic_questions_hash_lookup
ON topic_questions USING GIN (
    (question_data->>'hash') gin_trgm_ops
);

-- Composite GIN index for common query patterns
CREATE INDEX IF NOT EXISTS idx_topic_questions_composite
ON topic_questions USING GIN (
    grade,
    topic,
    difficulty,
    question_data
);

-- Update statistics
ANALYZE topic_questions;

-- =====================================================
-- Additional Performance Indexes
-- =====================================================

-- Index for user quiz history lookups (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'user_quiz_history') THEN
        CREATE INDEX IF NOT EXISTS idx_user_quiz_history_lookup
        ON user_quiz_history (user_id, topic, answered_at DESC);

        -- Index for question hash lookups
        CREATE INDEX IF NOT EXISTS idx_user_quiz_history_hash
        ON user_quiz_history (question_hash);

        -- Partial index for recent quiz history (last 30 days)
        CREATE INDEX IF NOT EXISTS idx_user_quiz_history_recent
        ON user_quiz_history (user_id, answered_at DESC)
        WHERE answered_at > NOW() - INTERVAL '30 days';

        -- Update statistics
        ANALYZE user_quiz_history;
    END IF;
END $$;

-- Index for quiz requests analytics (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'quiz_requests') THEN
        CREATE INDEX IF NOT EXISTS idx_quiz_requests_analytics
        ON quiz_requests (request_date, grade, difficulty);

        ANALYZE quiz_requests;
    END IF;
END $$;

-- Index for complete quizzes lookups (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'complete_quizzes') THEN
        CREATE INDEX IF NOT EXISTS idx_complete_quizzes_lookup
        ON complete_quizzes (grade, difficulty, topics_hash);

        ANALYZE complete_quizzes;
    END IF;
END $$;

-- =====================================================
-- 2.2 Materialized Views for Analytics
-- NOTE: These will only be created if the tables exist
-- =====================================================

-- Materialized view for user statistics
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'user_quiz_history') THEN
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_stats AS
        SELECT
            user_id,
            COUNT(*) as total_questions,
            SUM(was_correct) as correct_count,
            ROUND(SUM(was_correct) * 100.0 / COUNT(*), 2) as accuracy,
            COUNT(DISTINCT topic) as topics_attempted,
            COUNT(DISTINCT DATE(answered_at)) as active_days,
            MAX(answered_at) as last_activity
        FROM user_quiz_history
        GROUP BY user_id;

        -- Index on materialized view
        CREATE INDEX IF NOT EXISTS idx_mv_user_stats_user_id ON mv_user_stats(user_id);
    END IF;
END $$;

-- Materialized view for topic performance
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'user_quiz_history') THEN
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_topic_performance AS
        SELECT
            topic,
            COUNT(*) as total_attempts,
            SUM(was_correct) as correct_count,
            ROUND(SUM(was_correct) * 100.0 / COUNT(*), 2) as accuracy,
            AVG(time_spent) as avg_time
        FROM user_quiz_history
        GROUP BY topic;

        -- Index on topic performance view
        CREATE INDEX IF NOT EXISTS idx_mv_topic_performance_topic ON mv_topic_performance(topic);
    END IF;
END $$;

-- Materialized view for daily statistics
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'user_quiz_history') THEN
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_stats AS
        SELECT
            DATE(answered_at) as date,
            COUNT(*) as total_questions,
            SUM(was_correct) as correct_count,
            ROUND(SUM(was_correct) * 100.0 / COUNT(*), 2) as accuracy,
            COUNT(DISTINCT user_id) as unique_users
        FROM user_quiz_history
        GROUP BY DATE(answered_at);

        -- Index on daily stats
        CREATE INDEX IF NOT EXISTS idx_mv_daily_stats_date ON mv_daily_stats(date);
    END IF;
END $$;

-- Refresh function (call periodically)
CREATE OR REPLACE FUNCTION refresh_user_stats()
RETURNS void AS $$
BEGIN
    IF EXISTS (SELECT FROM pg_matviews WHERE matviewname = 'mv_user_stats') THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_stats;
    END IF;
    IF EXISTS (SELECT FROM pg_matviews WHERE matviewname = 'mv_topic_performance') THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_topic_performance;
    END IF;
    IF EXISTS (SELECT FROM pg_matviews WHERE matviewname = 'mv_daily_stats') THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_stats;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 2.1 Table Partitioning for user_quiz_history
-- NOTE: This is a template for future partitioning
-- =====================================================

-- To implement partitioning on an existing table:
-- 1. Create new partitioned table
-- 2. Migrate data
-- 3. Rename tables
-- 4. Update application to use new table

-- Template for partitioned table:
/*
CREATE TABLE user_quiz_history_partitioned (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id INTEGER NOT NULL,
    question_hash VARCHAR(32) NOT NULL,
    topic VARCHAR(255) NOT NULL,
    was_correct SMALLINT NOT NULL,
    time_spent INTEGER DEFAULT 0,
    answered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, answered_at)
) PARTITION BY RANGE (answered_at);
*/

-- Automated partition creation function
CREATE OR REPLACE FUNCTION create_monthly_partition()
RETURNS void AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    partition_date := DATE_TRUNC('month', NOW() + INTERVAL '1 month');
    partition_name := 'user_quiz_history_' || TO_CHAR(partition_date, 'YYYY_MM');
    start_date := TO_CHAR(partition_date, 'YYYY-MM-DD');
    end_date := TO_CHAR(partition_date + INTERVAL '1 month', 'YYYY-MM-DD');

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF user_quiz_history_partitioned FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;
