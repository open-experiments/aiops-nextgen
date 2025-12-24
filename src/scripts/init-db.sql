-- Database initialization script for AIOps NextGen
--
-- Spec Reference: specs/08-integration-matrix.md Section 6.1
--
-- Schema Structure:
--   clusters    - owned by cluster-registry service
--   intelligence - owned by intelligence-engine service

-- Create schemas
CREATE SCHEMA IF NOT EXISTS clusters;
CREATE SCHEMA IF NOT EXISTS intelligence;

-- Grant permissions (for development, all permissions to aiops user)
GRANT ALL PRIVILEGES ON SCHEMA clusters TO aiops;
GRANT ALL PRIVILEGES ON SCHEMA intelligence TO aiops;

-- Set default search path
ALTER DATABASE aiops SET search_path TO public, clusters, intelligence;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'AIOps NextGen database initialized with schemas: clusters, intelligence';
END $$;
