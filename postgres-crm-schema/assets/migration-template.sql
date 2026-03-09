-- Migration: NNN_description.sql
-- Date: YYYY-MM-DD
-- Description: [Brief description of what this migration does]
-- Author: [name]
--
-- IMPORTANT:
--   1. Use IF NOT EXISTS / IF EXISTS for idempotency
--   2. Update production/database/schema.sql after applying
--   3. Update postgres-crm-schema SKILL.md if adding new tables/columns
--   4. Use TIMESTAMPTZ (not TIMESTAMP), JSONB (not JSON), UUID (not SERIAL)

-- ============================================================
-- UP: Apply migration
-- ============================================================

-- Example: Add a new column
-- ALTER TABLE table_name ADD COLUMN IF NOT EXISTS column_name TYPE DEFAULT value;

-- Example: Create a new table
-- CREATE TABLE IF NOT EXISTS new_table (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     ... columns ...
--     created_at TIMESTAMPTZ DEFAULT NOW(),
--     updated_at TIMESTAMPTZ DEFAULT NOW()
-- );

-- Example: Add an index
-- CREATE INDEX IF NOT EXISTS idx_name ON table_name(column_name);

-- Example: Add an index without locking (production)
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table_name(column_name);

-- ============================================================
-- DOWN: Rollback migration (manual — run only if rolling back)
-- ============================================================

-- Example: Drop column
-- ALTER TABLE table_name DROP COLUMN IF EXISTS column_name;

-- Example: Drop table
-- DROP TABLE IF EXISTS new_table;

-- Example: Drop index
-- DROP INDEX IF EXISTS idx_name;
