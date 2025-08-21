-- ODIN Research Engine Database Schema
-- Initialize tables for projects, experiments, datasets, runs, and receipts

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    tier VARCHAR(20) DEFAULT 'free',
    quota_requests_used INTEGER DEFAULT 0,
    quota_requests_limit INTEGER DEFAULT 1000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- BYOK tokens table (short-lived, cleaned up by TTL)
CREATE TABLE IF NOT EXISTS byok_tokens (
    token VARCHAR(100) PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    encrypted_key TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Experiments table
CREATE TABLE IF NOT EXISTS experiments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    experiment_id VARCHAR(100) NOT NULL,
    variant VARCHAR(10) NOT NULL,
    goal TEXT,
    rollout_pct INTEGER DEFAULT 10,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(project_id, experiment_id)
);

-- Datasets table
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    format VARCHAR(10) NOT NULL,
    size_bytes BIGINT NOT NULL,
    record_count INTEGER NOT NULL,
    content_hash VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Runs table
CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    experiment_id UUID REFERENCES experiments(id) ON DELETE SET NULL,
    dataset_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'queued',
    realm VARCHAR(50) DEFAULT 'business',
    map_id VARCHAR(100),
    router_policy VARCHAR(100),
    metrics JSONB,
    receipt_chain JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Receipts table for audit trail
CREATE TABLE IF NOT EXISTS receipts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    trace_id VARCHAR(100) NOT NULL,
    receipt_type VARCHAR(50) NOT NULL,
    cid VARCHAR(100) NOT NULL,
    content JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rate limiting table (in-memory alternative to Redis)
CREATE TABLE IF NOT EXISTS rate_limits (
    key VARCHAR(200) PRIMARY KEY,
    count INTEGER DEFAULT 0,
    window_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);
CREATE INDEX IF NOT EXISTS idx_byok_tokens_expires_at ON byok_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_experiments_project_id ON experiments(project_id);
CREATE INDEX IF NOT EXISTS idx_datasets_project_id ON datasets(project_id);
CREATE INDEX IF NOT EXISTS idx_runs_project_id ON runs(project_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_receipts_run_id ON receipts(run_id);
CREATE INDEX IF NOT EXISTS idx_receipts_trace_id ON receipts(trace_id);
CREATE INDEX IF NOT EXISTS idx_rate_limits_window_start ON rate_limits(window_start);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Cleanup functions for expired data
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM byok_tokens WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cleanup_old_rate_limits()
RETURNS void AS $$
BEGIN
    DELETE FROM rate_limits WHERE window_start < NOW() - INTERVAL '1 hour';
END;
$$ LANGUAGE plpgsql;

-- Insert sample data for development
INSERT INTO projects (id, name, description, tier) VALUES 
    (uuid_generate_v4(), 'Demo Project', 'Sample research project for testing', 'free')
ON CONFLICT DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO odin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO odin;
