# Tool Implementation Patterns

Detailed patterns for building channel-aware MCP tools using the OpenAI Agents SDK.

---

## Full Tool Implementation Example

### `search_knowledge_base` — Complete Implementation

```python
from agents import function_tool
from pydantic import BaseModel, Field
from enum import Enum
from production.database.queries import search_kb_by_embedding, get_embedding
from production.agent.formatters import adapt_response


class Channel(str, Enum):
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class ChannelMetadata(BaseModel):
    channel_source: Channel
    customer_id: str
    conversation_id: str | None = None
    thread_id: str | None = None


class KnowledgeSearchInput(BaseModel):
    """Search product knowledge base for relevant documentation."""
    query: str = Field(description="Search query from customer message")
    max_results: int = Field(default=5, le=5, description="Max results to return")
    category: str | None = Field(default=None, description="Filter by doc category")
    channel: ChannelMetadata


class KnowledgeSearchOutput(BaseModel):
    results: list[dict]
    total_found: int
    query_used: str


@function_tool
async def search_knowledge_base(input: KnowledgeSearchInput) -> str:
    """Search the product knowledge base for relevant documentation.

    Channel-aware: adjusts result verbosity per channel.
    Must be called AFTER create_ticket and get_customer_history.
    """
    # 1. Generate embedding for the query
    embedding = await get_embedding(input.query)

    # 2. Search with pgvector cosine similarity
    results = await search_kb_by_embedding(
        embedding=embedding,
        max_results=input.max_results,
        category=input.category,
    )

    # 3. Format results based on channel
    if not results:
        return adapt_response(
            "I wasn't able to find specific documentation for your question. "
            "Let me search with different terms.",
            input.channel.channel_source,
        )

    # 4. Build response from results
    response_parts = []
    for r in results:
        response_parts.append(f"**{r['title']}**: {r['content'][:200]}")

    raw_response = "\n\n".join(response_parts)
    return adapt_response(raw_response, input.channel.channel_source)
```

### `create_ticket` — Complete Implementation

```python
class TicketInput(BaseModel):
    """Create a support ticket for this interaction."""
    customer_id: str
    issue: str = Field(description="Customer's issue description")
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    category: str | None = Field(
        default=None,
        pattern="^(general|technical|billing|feedback|bug_report)$",
    )
    channel: ChannelMetadata


@function_tool
async def create_ticket(input: TicketInput) -> str:
    """Create a support ticket. MUST be called first in every interaction.

    Channel-aware: records channel_source for routing and metrics.
    """
    from production.database.queries import insert_ticket

    ticket = await insert_ticket(
        customer_id=input.customer_id,
        issue=input.issue,
        priority=input.priority,
        category=input.category,
        channel=input.channel.channel_source.value,
        conversation_id=input.channel.conversation_id,
    )

    return f"Ticket created: {ticket['id']}"
```

### `get_customer_history` — Complete Implementation

```python
class CustomerHistoryInput(BaseModel):
    """Retrieve customer's cross-channel interaction history."""
    customer_id: str
    channel: ChannelMetadata


@function_tool
async def get_customer_history(input: CustomerHistoryInput) -> str:
    """Retrieve last 20 messages across all channels for context.

    Called AFTER create_ticket, BEFORE search_knowledge_base.
    """
    from production.database.queries import get_recent_messages

    messages = await get_recent_messages(
        customer_id=input.customer_id,
        limit=20,
    )

    if not messages:
        return "No previous interaction history found for this customer."

    history_parts = []
    for msg in messages:
        sender = "Customer" if msg["sender_type"] == "customer" else "Agent"
        channel = msg["channel"]
        history_parts.append(f"[{channel}] {sender}: {msg['content'][:100]}")

    return "\n".join(history_parts)
```

### `escalate_to_human` — Complete Implementation

```python
class EscalationInput(BaseModel):
    """Escalate ticket to human support agent."""
    ticket_id: str
    reason: str = Field(description="Why escalation is needed")
    urgency: str = Field(default="normal", pattern="^(normal|urgent|critical)$")
    channel: ChannelMetadata


@function_tool
async def escalate_to_human(input: EscalationInput) -> str:
    """Hand off to human support. Publishes Kafka event to fte.escalations.

    Channel-aware: includes channel_source for routing to correct team.
    """
    from production.database.queries import update_ticket_status
    from production.workers.kafka_producer import publish_escalation

    # Update ticket status
    await update_ticket_status(input.ticket_id, status="escalated")

    # Publish escalation event
    await publish_escalation(
        ticket_id=input.ticket_id,
        reason=input.reason,
        urgency=input.urgency,
        channel=input.channel.channel_source.value,
        customer_id=input.channel.customer_id,
    )

    return f"Escalated ticket {input.ticket_id} to human support. Reason: {input.reason}"
```

### `send_response` — Complete Implementation

```python
class ResponseInput(BaseModel):
    """Send response to customer via the correct channel."""
    ticket_id: str
    message: str = Field(description="Response message to send")
    channel: ChannelMetadata


@function_tool
async def send_response(input: ResponseInput) -> str:
    """Send formatted response via the correct channel. MUST be called last.

    Channel-aware: formats message per channel limits and style.
    """
    from production.agent.formatters import adapt_response
    from production.database.queries import store_message
    from production.workers.kafka_producer import publish_response

    # 1. Adapt response to channel
    formatted = adapt_response(input.message, input.channel.channel_source)

    # 2. Store in database
    await store_message(
        conversation_id=input.channel.conversation_id,
        sender_type="agent",
        content=formatted,
        channel=input.channel.channel_source.value,
    )

    # 3. Publish for delivery
    await publish_response(
        ticket_id=input.ticket_id,
        message=formatted,
        channel=input.channel.channel_source.value,
        customer_id=input.channel.customer_id,
        thread_id=input.channel.thread_id,
    )

    return f"Response sent via {input.channel.channel_source.value}"
```

---

## Error Handling Patterns

### Database Failure

```python
@function_tool
async def create_ticket(input: TicketInput) -> str:
    try:
        ticket = await insert_ticket(...)
        return f"Ticket created: {ticket['id']}"
    except ConnectionError:
        # DB is down — do not proceed to send_response
        return "ERROR: Unable to create ticket. Database connection failed. Retry or escalate."
    except IntegrityError:
        # Duplicate or constraint violation
        return "ERROR: Ticket creation failed due to data conflict. Check customer_id validity."
```

### API Timeout

```python
@function_tool
async def search_knowledge_base(input: KnowledgeSearchInput) -> str:
    try:
        results = await asyncio.wait_for(
            search_kb_by_embedding(embedding, input.max_results),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        return "Knowledge base search timed out. Attempting with simplified query."
```

### Missing Customer

```python
@function_tool
async def get_customer_history(input: CustomerHistoryInput) -> str:
    customer = await get_customer_by_id(input.customer_id)
    if customer is None:
        return "No customer record found. This appears to be a new customer."
```

---

## Testing Patterns

### Mocking Database Calls

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_create_ticket_success():
    mock_ticket = {"id": "ticket_123", "status": "open"}

    with patch("production.database.queries.insert_ticket", new_callable=AsyncMock) as mock_insert:
        mock_insert.return_value = mock_ticket

        result = await create_ticket(TicketInput(
            customer_id="cust_001",
            issue="Account locked",
            priority="high",
            channel=ChannelMetadata(
                channel_source=Channel.GMAIL,
                customer_id="cust_001",
            ),
        ))

        assert "ticket_123" in result
        mock_insert.assert_called_once()
```

### Mocking Kafka

```python
@pytest.mark.asyncio
async def test_escalate_publishes_kafka_event():
    with patch("production.workers.kafka_producer.publish_escalation", new_callable=AsyncMock) as mock_pub:
        result = await escalate_to_human(EscalationInput(
            ticket_id="ticket_123",
            reason="legal_mention",
            urgency="urgent",
            channel=ChannelMetadata(
                channel_source=Channel.WHATSAPP,
                customer_id="cust_001",
            ),
        ))

        mock_pub.assert_called_once_with(
            ticket_id="ticket_123",
            reason="legal_mention",
            urgency="urgent",
            channel="whatsapp",
            customer_id="cust_001",
        )
```

---

## Anti-Patterns

### Tool Without Channel Metadata

```python
# WRONG — missing ChannelMetadata
class BadSearchInput(BaseModel):
    query: str
    max_results: int = 5

# CORRECT — includes ChannelMetadata
class GoodSearchInput(BaseModel):
    query: str
    max_results: int = Field(default=5, le=5)
    channel: ChannelMetadata
```

### Breaking Execution Order

```python
# WRONG — send_response before create_ticket
tools = [send_response, search_knowledge_base, create_ticket]

# CORRECT — enforced order
# create_ticket -> get_customer_history -> search_knowledge_base -> send_response
```

### Hardcoded Response (No Channel Adaptation)

```python
# WRONG — same response for all channels
@function_tool
async def bad_tool(input: ToolInput) -> str:
    return "Here is your answer: ..."

# CORRECT — adapted per channel
@function_tool
async def good_tool(input: ToolInput) -> str:
    raw = "Here is your answer: ..."
    return adapt_response(raw, input.channel.channel_source)
```

### Direct SQL in Tool

```python
# WRONG — SQL in tool function
@function_tool
async def bad_tool(input: ToolInput) -> str:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tickets WHERE id = $1", input.ticket_id)

# CORRECT — use queries.py
@function_tool
async def good_tool(input: ToolInput) -> str:
    ticket = await get_ticket_by_id(input.ticket_id)
```
