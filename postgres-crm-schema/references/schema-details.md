# Schema Details Reference

Comprehensive documentation for the Customer Success FTE PostgreSQL CRM schema.

---

## Entity Relationship Diagram

```
┌──────────────┐       ┌─────────────────────┐
│  customers   │──1:N──│ customer_identifiers │
│              │       │  (email/phone/wa)    │
└──────┬───────┘       └─────────────────────┘
       │
       ├──1:N──┌────────────────┐
       │       │ conversations  │──1:N──┌──────────┐
       │       │ (per channel)  │       │ messages  │
       │       └────────┬───────┘       └──────────┘
       │                │
       ├──1:N──┌────────┴───────┐
       │       │    tickets     │──0:N──┌───────────────┐
       │       │ (per interact) │       │ agent_metrics  │
       │       └────────────────┘       └───────────────┘
       │
       │       ┌────────────────┐       ┌────────────────┐
       │       │ knowledge_base │       │ channel_configs │
       │       │ (pgvector)     │       │ (per channel)   │
       │       └────────────────┘       └────────────────┘
```

## Foreign Key Chains

```
customers.id
  ├── customer_identifiers.customer_id (CASCADE delete)
  ├── conversations.customer_id
  └── tickets.customer_id

conversations.id
  ├── messages.conversation_id
  └── tickets.conversation_id

tickets.id
  └── agent_metrics.ticket_id
```

---

## Column-Level Documentation

### `customers`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | UUID | PK, gen_random_uuid() | Unique customer identifier |
| name | VARCHAR(255) | nullable | Customer display name |
| email | VARCHAR(255) | UNIQUE, nullable | Primary email (also in customer_identifiers) |
| phone | VARCHAR(50) | nullable | Primary phone number |
| company | VARCHAR(255) | nullable | Company/organization name |
| metadata | JSONB | DEFAULT '{}' | Flexible extra data (see JSONB conventions below) |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation timestamp |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Last modification timestamp |

**Indexes:** `idx_customers_email` (email lookup), `idx_customers_phone` (phone lookup)

### `customer_identifiers`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | UUID | PK, gen_random_uuid() | Row identifier |
| customer_id | UUID | FK -> customers(id) CASCADE | Links to unified customer |
| identifier_type | VARCHAR(20) | NOT NULL | One of: `email`, `phone`, `whatsapp` |
| identifier_value | VARCHAR(255) | NOT NULL | The actual email/phone/whatsapp ID |
| verified | BOOLEAN | DEFAULT FALSE | Whether identity has been confirmed |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | When identifier was first seen |

**Constraints:** UNIQUE(identifier_type, identifier_value) — same identifier can't map to two customers
**Indexes:** `idx_ci_lookup` (type + value for fast resolution), `idx_ci_customer` (find all identifiers for a customer)

### `conversations`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | UUID | PK, gen_random_uuid() | Conversation thread ID |
| customer_id | UUID | FK -> customers(id), NOT NULL | Who the conversation is with |
| channel | VARCHAR(20) | NOT NULL | `gmail`, `whatsapp`, or `web_form` |
| status | VARCHAR(20) | DEFAULT 'active' | `active`, `resolved`, or `escalated` |
| sentiment_score | FLOAT | nullable | Rolling sentiment for this conversation |
| thread_id | VARCHAR(255) | nullable | Gmail thread_id for email continuity |
| started_at | TIMESTAMPTZ | DEFAULT NOW() | When conversation began |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Last activity in conversation |

**Indexes:** `idx_conv_customer`, `idx_conv_channel`, `idx_conv_thread`

### `messages`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | UUID | PK, gen_random_uuid() | Message ID |
| conversation_id | UUID | FK -> conversations(id), NOT NULL | Parent conversation |
| sender_type | VARCHAR(10) | NOT NULL | `customer` or `agent` |
| content | TEXT | NOT NULL | Message body |
| channel | VARCHAR(20) | NOT NULL | Which channel this message came from |
| delivery_status | VARCHAR(20) | DEFAULT 'pending' | `pending`, `sent`, `delivered`, `failed` |
| metadata | JSONB | DEFAULT '{}' | Channel-specific metadata (see conventions) |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | When message was created/received |

**Indexes:** `idx_msg_conversation`, `idx_msg_created`

### `tickets`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | UUID | PK, gen_random_uuid() | Ticket ID |
| conversation_id | UUID | FK -> conversations(id), nullable | Related conversation |
| customer_id | UUID | FK -> customers(id), NOT NULL | Ticket owner |
| subject | VARCHAR(500) | nullable | Ticket subject/title |
| issue | TEXT | NOT NULL | Customer's issue description |
| category | VARCHAR(50) | nullable | `general`, `technical`, `billing`, `feedback`, `bug_report` |
| priority | VARCHAR(20) | DEFAULT 'medium' | `low`, `medium`, `high` |
| status | VARCHAR(20) | DEFAULT 'open' | `open`, `in_progress`, `resolved`, `escalated` |
| channel | VARCHAR(20) | NOT NULL | Channel where ticket originated |
| assigned_to | VARCHAR(255) | nullable | Human agent name if escalated |
| resolved_at | TIMESTAMPTZ | nullable | When ticket was resolved |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Ticket creation time |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Last ticket update |

**Indexes:** `idx_tickets_customer`, `idx_tickets_status`, `idx_tickets_channel`

### `knowledge_base`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | UUID | PK, gen_random_uuid() | Document ID |
| title | VARCHAR(500) | NOT NULL | Document title |
| content | TEXT | NOT NULL | Full document content |
| category | VARCHAR(100) | nullable | Document category for filtering |
| embedding | vector(1536) | nullable | OpenAI text-embedding-ada-002 vector |
| metadata | JSONB | DEFAULT '{}' | Extra doc metadata |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | When document was added |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Last document update |

**Indexes:** `idx_kb_category`, `idx_kb_embedding` (IVFFlat for cosine similarity)

### `channel_configs`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | UUID | PK, gen_random_uuid() | Config row ID |
| channel | VARCHAR(20) | UNIQUE, NOT NULL | Channel name |
| enabled | BOOLEAN | DEFAULT TRUE | Whether channel is active |
| api_config | JSONB | DEFAULT '{}' | API credentials reference (NOT raw secrets) |
| response_template | JSONB | DEFAULT '{}' | Greeting, signature, formatting rules |
| max_response_length | INTEGER | nullable | Char/word limit for this channel |
| metadata | JSONB | DEFAULT '{}' | Extra config |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Config creation time |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Last config update |

### `agent_metrics`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | UUID | PK, gen_random_uuid() | Metric row ID |
| channel | VARCHAR(20) | NOT NULL | Channel this metric is for |
| metric_type | VARCHAR(50) | NOT NULL | `response_time`, `accuracy`, `escalation_rate`, `sentiment` |
| metric_value | FLOAT | NOT NULL | Numeric metric value |
| ticket_id | UUID | FK -> tickets(id), nullable | Associated ticket if applicable |
| metadata | JSONB | DEFAULT '{}' | Extra metric context |
| recorded_at | TIMESTAMPTZ | DEFAULT NOW() | When metric was recorded |

**Indexes:** `idx_metrics_channel`, `idx_metrics_type`, `idx_metrics_recorded`

---

## Index Strategy

| Index | Table | Why |
|-------|-------|-----|
| `idx_customers_email` | customers | Fast customer lookup by email (login, dedup) |
| `idx_customers_phone` | customers | Fast customer lookup by phone |
| `idx_ci_lookup` | customer_identifiers | Cross-channel identity resolution (type + value) |
| `idx_ci_customer` | customer_identifiers | Find all identifiers for a customer |
| `idx_conv_customer` | conversations | Get all conversations for a customer |
| `idx_conv_channel` | conversations | Filter conversations by channel |
| `idx_conv_thread` | conversations | Gmail thread_id lookup for continuity |
| `idx_msg_conversation` | messages | Get all messages in a conversation |
| `idx_msg_created` | messages | Time-ordered message retrieval |
| `idx_tickets_customer` | tickets | Get all tickets for a customer |
| `idx_tickets_status` | tickets | Filter by ticket status (open/resolved/etc) |
| `idx_tickets_channel` | tickets | Filter tickets by channel |
| `idx_kb_category` | knowledge_base | Filter docs by category before vector search |
| `idx_kb_embedding` | knowledge_base | IVFFlat index for fast cosine similarity search |
| `idx_metrics_channel` | agent_metrics | Filter metrics by channel |
| `idx_metrics_type` | agent_metrics | Filter by metric type |
| `idx_metrics_recorded` | agent_metrics | Time-range queries on metrics |

---

## JSONB Metadata Conventions

**Rule:** Core queryable data goes in dedicated columns. Flexible/optional data goes in `metadata`.

| Table | metadata Contains | Does NOT Contain |
|-------|-------------------|------------------|
| customers | Preferences, tags, notes, external IDs | name, email, phone (dedicated columns) |
| messages | Attachment URLs, original headers, media type | content, channel, sender_type (dedicated) |
| tickets | Internal notes, SLA timestamps, tag arrays | issue, priority, status (dedicated) |
| knowledge_base | Source URL, last_reviewed date, author | title, content, category (dedicated) |
| channel_configs | Rate limits, retry config, feature flags | channel, enabled, max_response_length (dedicated) |
| agent_metrics | Token counts, model version, tool call list | metric_value, metric_type, channel (dedicated) |

---

## pgvector Setup

```sql
-- Enable the extension (requires superuser once)
CREATE EXTENSION IF NOT EXISTS vector;

-- The embedding column uses 1536 dimensions (OpenAI text-embedding-ada-002)
-- For text-embedding-3-small use 1536, for text-embedding-3-large use 3072

-- IVFFlat index for approximate nearest neighbor search
-- Lists parameter: sqrt(total_rows) is a good starting point
CREATE INDEX idx_kb_embedding ON knowledge_base
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Semantic search query pattern
SELECT id, title, content, 1 - (embedding <=> $1::vector) AS similarity
FROM knowledge_base
WHERE category = $2 OR $2 IS NULL
ORDER BY embedding <=> $1::vector
LIMIT $3;
```

---

## Channel Enum Values

Used consistently across: `conversations.channel`, `messages.channel`, `tickets.channel`, `channel_configs.channel`, `agent_metrics.channel`.

| Value | Channel |
|-------|---------|
| `gmail` | Email via Gmail API |
| `whatsapp` | WhatsApp via Twilio |
| `web_form` | Web support form |

**Important:** Always use these exact strings. Never `email`, `wa`, `webform`, or other variants.

---

## Cross-Channel Identity Resolution Flow

```
1. Incoming message arrives with identifier (email or phone)
2. Query customer_identifiers:
   SELECT customer_id FROM customer_identifiers
   WHERE identifier_type = $1 AND identifier_value = $2

3a. If found → return customer_id, load merged history
3b. If NOT found:
    - Check customers table for direct email/phone match
    - If customer exists → create new identifier row, link to customer
    - If customer doesn't exist → create new customer + identifier

4. Load conversation history across ALL channels for this customer_id
5. Return unified customer context to the agent
```
