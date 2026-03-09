---
name: postgres-crm-schema
description: |
  Enforce the canonical PostgreSQL CRM schema for the Customer Success FTE system. This skill
  should be used when creating or modifying database tables, writing migrations, building queries,
  or reviewing schema changes — to prevent rogue columns, schema drift, and ensure all database
  work aligns with the authoritative table definitions for customers, customer_identifiers,
  conversations, messages, tickets, knowledge_base, channel_configs, and agent_metrics.
---

# PostgreSQL CRM Schema

Enforce the canonical CRM schema. All database work MUST reference these definitions.

## Before Implementation

Gather context before any schema work:

| Source | Gather |
|--------|--------|
| **Codebase** | `production/database/schema.sql`, existing migrations in `production/database/migrations/` |
| **Conversation** | What schema change is needed, why |
| **AGENTS.md** | Table purposes, channel constraints, data flow |

## Canonical Schema

These are the authoritative table definitions. **Never add columns, rename fields, or change types without updating this skill.**

### `customers`

Primary customer record. One row per unique customer.

```sql
CREATE TABLE customers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255),
    email           VARCHAR(255) UNIQUE,
    phone           VARCHAR(50),
    company         VARCHAR(255),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_phone ON customers(phone);
```

### `customer_identifiers`

Cross-channel identity mapping. Links email/phone/whatsapp to a unified customer.

```sql
CREATE TABLE customer_identifiers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    identifier_type VARCHAR(20) NOT NULL,  -- 'email' | 'phone' | 'whatsapp'
    identifier_value VARCHAR(255) NOT NULL,
    verified        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(identifier_type, identifier_value)
);

CREATE INDEX idx_ci_lookup ON customer_identifiers(identifier_type, identifier_value);
CREATE INDEX idx_ci_customer ON customer_identifiers(customer_id);
```

### `conversations`

Conversation threads. One per customer-channel interaction session.

```sql
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    channel         VARCHAR(20) NOT NULL,  -- 'gmail' | 'whatsapp' | 'web_form'
    status          VARCHAR(20) DEFAULT 'active',  -- 'active' | 'resolved' | 'escalated'
    sentiment_score FLOAT,
    thread_id       VARCHAR(255),  -- Gmail thread_id for continuity
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conv_customer ON conversations(customer_id);
CREATE INDEX idx_conv_channel ON conversations(channel);
CREATE INDEX idx_conv_thread ON conversations(thread_id);
```

### `messages`

All messages across all channels. Both customer and agent messages.

```sql
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    sender_type     VARCHAR(10) NOT NULL,  -- 'customer' | 'agent'
    content         TEXT NOT NULL,
    channel         VARCHAR(20) NOT NULL,  -- 'gmail' | 'whatsapp' | 'web_form'
    delivery_status VARCHAR(20) DEFAULT 'pending',  -- 'pending' | 'sent' | 'delivered' | 'failed'
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_msg_conversation ON messages(conversation_id);
CREATE INDEX idx_msg_created ON messages(created_at);
```

### `tickets`

Support tickets. One per customer interaction (create_ticket is always first tool call).

```sql
CREATE TABLE tickets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    subject         VARCHAR(500),
    issue           TEXT NOT NULL,
    category        VARCHAR(50),  -- 'general' | 'technical' | 'billing' | 'feedback' | 'bug_report'
    priority        VARCHAR(20) DEFAULT 'medium',  -- 'low' | 'medium' | 'high'
    status          VARCHAR(20) DEFAULT 'open',  -- 'open' | 'in_progress' | 'resolved' | 'escalated'
    channel         VARCHAR(20) NOT NULL,
    assigned_to     VARCHAR(255),  -- human agent if escalated
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tickets_customer ON tickets(customer_id);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_channel ON tickets(channel);
```

### `knowledge_base`

Product documentation with vector embeddings for semantic search (pgvector).

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_base (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(500) NOT NULL,
    content         TEXT NOT NULL,
    category        VARCHAR(100),
    embedding       vector(1536),  -- OpenAI ada-002 dimensions
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kb_category ON knowledge_base(category);
CREATE INDEX idx_kb_embedding ON knowledge_base USING ivfflat (embedding vector_cosine_ops);
```

### `channel_configs`

Per-channel settings and constraints.

```sql
CREATE TABLE channel_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel         VARCHAR(20) UNIQUE NOT NULL,
    enabled         BOOLEAN DEFAULT TRUE,
    api_config      JSONB DEFAULT '{}',    -- channel-specific API keys/endpoints (encrypted ref)
    response_template JSONB DEFAULT '{}',  -- greeting, signature, formatting rules
    max_response_length INTEGER,           -- character/word limit per channel
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### `agent_metrics`

Performance metrics per channel for monitoring and reporting.

```sql
CREATE TABLE agent_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel         VARCHAR(20) NOT NULL,
    metric_type     VARCHAR(50) NOT NULL,  -- 'response_time' | 'accuracy' | 'escalation_rate' | 'sentiment'
    metric_value    FLOAT NOT NULL,
    ticket_id       UUID REFERENCES tickets(id),
    metadata        JSONB DEFAULT '{}',
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metrics_channel ON agent_metrics(channel);
CREATE INDEX idx_metrics_type ON agent_metrics(metric_type);
CREATE INDEX idx_metrics_recorded ON agent_metrics(recorded_at);
```

## Schema Rules

### Adding Columns

1. Check this skill's canonical definition first
2. Write a migration file in `production/database/migrations/`
3. Update `production/database/schema.sql` to match
4. Update THIS skill's schema definition to stay in sync
5. Use `ALTER TABLE ... ADD COLUMN` with a sensible default

### Allowed Column Types

| Use Case | Type | Notes |
|----------|------|-------|
| Identifiers | `UUID` | Always `gen_random_uuid()` default |
| Short text | `VARCHAR(N)` | Set appropriate limit |
| Long text | `TEXT` | For message content, issue descriptions |
| Enum-like | `VARCHAR(20-50)` | With CHECK constraint or app-level validation |
| Timestamps | `TIMESTAMPTZ` | Always timezone-aware |
| Flexible data | `JSONB` | For metadata, configs — not for core fields |
| Numbers | `FLOAT` or `INTEGER` | As appropriate |
| Vectors | `vector(1536)` | Only for embeddings, requires pgvector |

### Migration Naming Convention

```
production/database/migrations/
  001_initial_schema.sql
  002_add_knowledge_base_embeddings.sql
  003_add_channel_configs.sql
```

Format: `{NNN}_{description}.sql` — sequential, descriptive, lowercase with underscores.

### Query Patterns

All database access goes through `production/database/queries.py`. Direct SQL in handlers or tools is forbidden.

```python
# Correct — use queries.py
from production.database.queries import get_customer_by_email
customer = await get_customer_by_email(email)

# Wrong — direct SQL in handler
cursor.execute("SELECT * FROM customers WHERE email = %s", (email,))
```

## Must Follow

- [ ] All tables match canonical definitions above
- [ ] Every migration has a corresponding update to `schema.sql`
- [ ] UUIDs for all primary keys
- [ ] `TIMESTAMPTZ` for all timestamps (never `TIMESTAMP`)
- [ ] `JSONB` for flexible metadata (never `JSON`)
- [ ] Indexes on all foreign keys and common query columns
- [ ] All DB access through `production/database/queries.py`
- [ ] `channel` column uses consistent enum values: `gmail`, `whatsapp`, `web_form`

## Must Avoid

- Adding columns not in the canonical schema without updating this skill
- Using `TIMESTAMP` instead of `TIMESTAMPTZ`
- Using `JSON` instead of `JSONB`
- Putting direct SQL queries in channel handlers or agent tools
- Creating new tables without documenting them here
- Using `SERIAL` or `BIGSERIAL` for IDs (use `UUID`)
- Storing secrets in `channel_configs.api_config` (use encrypted references)

## Validating Schema

Run the validation script to check a schema.sql against canonical definitions:

```bash
python scripts/validate-schema.py --schema production/database/schema.sql
```

Reports missing tables, missing columns, type mismatches, missing indexes, and extra columns/tables (drift).

## Creating Migrations

Copy `assets/migration-template.sql` to `production/database/migrations/{NNN}_{description}.sql` and fill in the UP/DOWN sections. See `references/migration-guide.md` for patterns.

## Reference Files

| File | When to Read |
|------|--------------|
| `references/schema-details.md` | ER diagram, column-level documentation for all 8 tables, index strategy, JSONB conventions, pgvector setup, cross-channel identity resolution flow |
| `references/migration-guide.md` | Migration naming, idempotent patterns (IF NOT EXISTS), UP/DOWN structure, common migration examples, testing locally, schema drift detection |
| `references/query-patterns.md` | Canonical asyncpg query patterns for all tables — CRUD, cross-channel lookup, conversation history, semantic search, metrics, SQL injection prevention |
| `scripts/validate-schema.py` | Run to validate schema.sql against canonical definitions — checks tables, columns, types, indexes, warns about drift |
| `assets/migration-template.sql` | Copy as starting point for new migration files with UP/DOWN sections and comments |
