# Query Patterns

Canonical query patterns for `production/database/queries.py`. All database access MUST go through this module.

---

## Connection Setup (asyncpg)

```python
import asyncpg

# Connection pool — initialize once at app startup
pool: asyncpg.Pool | None = None

async def init_db(dsn: str):
    global pool
    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=5,
        max_size=20,
        command_timeout=10,
    )

async def close_db():
    if pool:
        await pool.close()
```

---

## Customer Queries

### Get Customer by ID

```python
async def get_customer_by_id(customer_id: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM customers WHERE id = $1",
            customer_id,
        )
        return dict(row) if row else None
```

### Get Customer by Email

```python
async def get_customer_by_email(email: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM customers WHERE email = $1",
            email,
        )
        return dict(row) if row else None
```

### Create Customer

```python
async def create_customer(name: str, email: str = None, phone: str = None, company: str = None) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO customers (name, email, phone, company)
               VALUES ($1, $2, $3, $4)
               RETURNING *""",
            name, email, phone, company,
        )
        return dict(row)
```

---

## Cross-Channel Identity Resolution

### Resolve Customer by Identifier

```python
async def resolve_customer(identifier_type: str, identifier_value: str) -> dict | None:
    """Look up unified customer_id from any channel identifier."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT c.* FROM customers c
               JOIN customer_identifiers ci ON c.id = ci.customer_id
               WHERE ci.identifier_type = $1 AND ci.identifier_value = $2""",
            identifier_type, identifier_value,
        )
        return dict(row) if row else None
```

### Add Identifier to Customer

```python
async def add_customer_identifier(customer_id: str, identifier_type: str, identifier_value: str) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
               VALUES ($1, $2, $3)
               ON CONFLICT (identifier_type, identifier_value) DO NOTHING
               RETURNING *""",
            customer_id, identifier_type, identifier_value,
        )
        return dict(row) if row else None
```

---

## Conversation Queries

### Get or Create Conversation

```python
async def get_or_create_conversation(customer_id: str, channel: str, thread_id: str = None) -> dict:
    async with pool.acquire() as conn:
        # Try to find active conversation
        row = await conn.fetchrow(
            """SELECT * FROM conversations
               WHERE customer_id = $1 AND channel = $2 AND status = 'active'
               ORDER BY updated_at DESC LIMIT 1""",
            customer_id, channel,
        )
        if row:
            return dict(row)

        # Create new conversation
        row = await conn.fetchrow(
            """INSERT INTO conversations (customer_id, channel, thread_id)
               VALUES ($1, $2, $3) RETURNING *""",
            customer_id, channel, thread_id,
        )
        return dict(row)
```

---

## Message Queries

### Get Recent Messages (Last 20)

```python
async def get_recent_messages(customer_id: str, limit: int = 20) -> list[dict]:
    """Get last N messages across all channels for a customer."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT m.* FROM messages m
               JOIN conversations c ON m.conversation_id = c.id
               WHERE c.customer_id = $1
               ORDER BY m.created_at DESC
               LIMIT $2""",
            customer_id, limit,
        )
        return [dict(r) for r in rows]
```

### Store Message

```python
async def store_message(conversation_id: str, sender_type: str, content: str, channel: str, metadata: dict = None) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO messages (conversation_id, sender_type, content, channel, metadata)
               VALUES ($1, $2, $3, $4, $5::jsonb)
               RETURNING *""",
            conversation_id, sender_type, content, channel,
            json.dumps(metadata or {}),
        )
        return dict(row)
```

---

## Ticket Queries

### Create Ticket

```python
async def insert_ticket(customer_id: str, issue: str, channel: str, priority: str = "medium",
                        category: str = None, conversation_id: str = None) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO tickets (customer_id, issue, channel, priority, category, conversation_id)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING *""",
            customer_id, issue, channel, priority, category, conversation_id,
        )
        return dict(row)
```

### Update Ticket Status

```python
async def update_ticket_status(ticket_id: str, status: str, assigned_to: str = None) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE tickets SET status = $2, assigned_to = $3,
               updated_at = NOW(),
               resolved_at = CASE WHEN $2 = 'resolved' THEN NOW() ELSE resolved_at END
               WHERE id = $1 RETURNING *""",
            ticket_id, status, assigned_to,
        )
        return dict(row)
```

---

## Knowledge Base Queries

### Semantic Search with pgvector

```python
async def search_kb_by_embedding(embedding: list[float], max_results: int = 5, category: str = None) -> list[dict]:
    """Search knowledge base by cosine similarity."""
    async with pool.acquire() as conn:
        if category:
            rows = await conn.fetch(
                """SELECT id, title, content, category,
                          1 - (embedding <=> $1::vector) AS similarity
                   FROM knowledge_base
                   WHERE category = $2
                   ORDER BY embedding <=> $1::vector
                   LIMIT $3""",
                str(embedding), category, max_results,
            )
        else:
            rows = await conn.fetch(
                """SELECT id, title, content, category,
                          1 - (embedding <=> $1::vector) AS similarity
                   FROM knowledge_base
                   ORDER BY embedding <=> $1::vector
                   LIMIT $2""",
                str(embedding), max_results,
            )
        return [dict(r) for r in rows]
```

---

## Metrics Queries

### Record Metric

```python
async def record_metric(channel: str, metric_type: str, metric_value: float,
                        ticket_id: str = None, metadata: dict = None) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO agent_metrics (channel, metric_type, metric_value, ticket_id, metadata)
               VALUES ($1, $2, $3, $4, $5::jsonb)
               RETURNING *""",
            channel, metric_type, metric_value, ticket_id,
            json.dumps(metadata or {}),
        )
        return dict(row)
```

### Get Aggregated Metrics

```python
async def get_metrics_summary(channel: str = None, hours: int = 24) -> list[dict]:
    """Get metric averages for the last N hours, optionally filtered by channel."""
    async with pool.acquire() as conn:
        query = """
            SELECT channel, metric_type,
                   AVG(metric_value) as avg_value,
                   COUNT(*) as sample_count
            FROM agent_metrics
            WHERE recorded_at > NOW() - INTERVAL '%s hours'
        """
        params = [hours]

        if channel:
            query += " AND channel = $2"
            params.append(channel)

        query += " GROUP BY channel, metric_type ORDER BY channel, metric_type"

        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]
```

---

## SQL Injection Prevention

**All queries use parameterized statements ($1, $2, ...) via asyncpg.** Never use string formatting:

```python
# CORRECT — parameterized
await conn.fetchrow("SELECT * FROM customers WHERE email = $1", email)

# WRONG — string formatting (SQL injection risk)
await conn.fetchrow(f"SELECT * FROM customers WHERE email = '{email}'")
```

asyncpg enforces parameterized queries at the protocol level. There is no way to accidentally concatenate user input into the query.
