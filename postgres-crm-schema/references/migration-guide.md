# Migration Guide

How to write, test, and manage database migrations for the Customer Success FTE CRM.

---

## File Naming Convention

```
production/database/migrations/
  001_initial_schema.sql
  002_add_knowledge_base_embeddings.sql
  003_add_channel_configs.sql
  004_add_customer_company_field.sql
```

Format: `{NNN}_{description}.sql`
- `NNN` — 3-digit sequential number (001, 002, ...)
- `description` — lowercase, underscores, describes the change
- Always increment from the highest existing migration number

---

## Migration File Structure

Every migration has UP (apply) and DOWN (rollback) sections:

```sql
-- Migration: NNN_description.sql
-- Date: YYYY-MM-DD
-- Description: Brief description of what this migration does
-- Author: [name]

-- ============================================================
-- UP: Apply migration
-- ============================================================

-- [SQL statements to apply the change]

-- ============================================================
-- DOWN: Rollback migration (manual — run only if rolling back)
-- ============================================================

-- [SQL statements to reverse the change]
```

---

## Idempotent Patterns

Always write migrations that can be safely re-run:

### Add Table

```sql
-- UP
CREATE TABLE IF NOT EXISTS new_table (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- DOWN
DROP TABLE IF EXISTS new_table;
```

### Add Column

```sql
-- UP
ALTER TABLE customers ADD COLUMN IF NOT EXISTS company VARCHAR(255);

-- DOWN
ALTER TABLE customers DROP COLUMN IF EXISTS company;
```

### Add Index

```sql
-- UP
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);

-- DOWN
DROP INDEX IF EXISTS idx_tickets_priority;
```

### Add Constraint

```sql
-- UP
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_ticket_priority'
    ) THEN
        ALTER TABLE tickets ADD CONSTRAINT chk_ticket_priority
            CHECK (priority IN ('low', 'medium', 'high'));
    END IF;
END $$;

-- DOWN
ALTER TABLE tickets DROP CONSTRAINT IF EXISTS chk_ticket_priority;
```

### Modify Enum-Like Column (add allowed value)

```sql
-- UP: Allow new category value (app-level validation, not DB constraint)
-- If using CHECK constraints:
ALTER TABLE tickets DROP CONSTRAINT IF EXISTS chk_ticket_category;
ALTER TABLE tickets ADD CONSTRAINT chk_ticket_category
    CHECK (category IN ('general', 'technical', 'billing', 'feedback', 'bug_report', 'new_category'));

-- DOWN
ALTER TABLE tickets DROP CONSTRAINT IF EXISTS chk_ticket_category;
ALTER TABLE tickets ADD CONSTRAINT chk_ticket_category
    CHECK (category IN ('general', 'technical', 'billing', 'feedback', 'bug_report'));
```

### Backfill Data

```sql
-- UP: Backfill new column with default values
UPDATE customers SET company = 'Unknown' WHERE company IS NULL;

-- DOWN: (cannot reliably undo backfill — document this)
-- WARNING: Backfill is not reversible. Previous NULL values cannot be restored.
```

---

## Common Migration Patterns

### Pattern 1: Add a New Column with Default

```sql
-- Migration: 004_add_ticket_tags.sql
-- Date: 2026-03-06
-- Description: Add JSONB tags column to tickets for flexible categorization

-- UP
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]';

-- DOWN
ALTER TABLE tickets DROP COLUMN IF EXISTS tags;
```

### Pattern 2: Add a New Table with Foreign Key

```sql
-- Migration: 005_add_escalation_log.sql
-- Date: 2026-03-06
-- Description: Track escalation history per ticket

-- UP
CREATE TABLE IF NOT EXISTS escalation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES tickets(id),
    reason TEXT NOT NULL,
    urgency VARCHAR(20) DEFAULT 'normal',
    escalated_by VARCHAR(50) DEFAULT 'agent',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_esclog_ticket ON escalation_log(ticket_id);

-- DOWN
DROP TABLE IF EXISTS escalation_log;
```

### Pattern 3: Add Index for Performance

```sql
-- Migration: 006_add_msg_channel_idx.sql
-- Date: 2026-03-06
-- Description: Add composite index for channel + created_at on messages for faster channel-filtered queries

-- UP
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_msg_channel_created
    ON messages(channel, created_at DESC);

-- DOWN
DROP INDEX IF EXISTS idx_msg_channel_created;
```

**Note:** Use `CONCURRENTLY` for production indexes to avoid table locks.

---

## Testing Migrations Locally

### With Docker

```bash
# Start local PostgreSQL
docker run -d --name fte-db -e POSTGRES_PASSWORD=test -p 5432:5432 postgres:16

# Apply all migrations in order
for f in production/database/migrations/*.sql; do
    echo "Applying: $f"
    psql -h localhost -U postgres -d postgres -f "$f"
done

# Verify schema matches expected state
psql -h localhost -U postgres -d postgres -c "\dt"  # list tables
psql -h localhost -U postgres -d postgres -c "\d customers"  # describe table
```

### Verify Against schema.sql

After applying all migrations, the database state should match `production/database/schema.sql` exactly. Compare with:

```bash
# Dump current schema
pg_dump -h localhost -U postgres -d postgres --schema-only > /tmp/actual_schema.sql

# Compare (manually or with diff)
diff production/database/schema.sql /tmp/actual_schema.sql
```

---

## Schema Drift Detection

Schema drift occurs when the database state diverges from `schema.sql` or the canonical definitions in this skill.

### Signs of Drift

- Columns in the database not present in schema.sql
- Different column types than defined
- Missing indexes
- Extra tables not documented

### Prevention

1. Every migration MUST have a corresponding update to `production/database/schema.sql`
2. Every schema change MUST update the canonical definitions in `postgres-crm-schema` SKILL.md
3. Run the validation script periodically: `python scripts/validate-schema.py --schema production/database/schema.sql`

---

## Rules

- Always increment migration numbers sequentially
- Never modify an existing migration that has been applied to any environment
- Always include both UP and DOWN sections
- Use `IF NOT EXISTS` / `IF EXISTS` for idempotency
- Use `CONCURRENTLY` for indexes on large production tables
- Update `schema.sql` and this skill's SKILL.md after every migration
- Test migrations locally before applying to production
