-- Smart Spectator Database Initialization
-- This runs once when the PostgreSQL container starts.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create the database if it doesn't exist (already handled by POSTGRES_DB env)
-- Set timezone
SET timezone = 'UTC';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE smart_spectator TO postgres;

-- Note: Tables are created by SQLAlchemy/Alembic at runtime.
-- This file is for database-level extensions and settings only.
