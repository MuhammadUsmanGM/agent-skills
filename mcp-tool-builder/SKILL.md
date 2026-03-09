---
name: mcp-tool-builder
description: |
  Build channel-aware MCP tools for the Customer Success FTE system. This skill should be
  used when creating, modifying, or reviewing MCP server tools that must accept channel_source
  metadata and format responses per channel (Gmail, WhatsApp, Web Form). Provides the canonical
  pattern for tool input schemas, channel adaptation, and the required tool execution order.
---

# MCP Tool Builder

Build channel-aware MCP tools following the Customer Success FTE canonical patterns.

## Before Implementation

Gather context to ensure correct integration:

| Source | Gather |
|--------|--------|
| **Codebase** | Existing tools in `production/agent/tools.py`, current schemas |
| **Conversation** | Which tool to build, specific requirements |
| **AGENTS.md** | Tool execution order, guardrails, channel constraints |
| **Skill References** | Tool patterns from `references/tool-patterns.md` |

## Channel-Aware Tool Pattern

Every MCP tool in this system MUST be channel-aware. This means:

1. Accept `channel_source` in the input schema
2. Pass channel context through the tool chain
3. Format output according to channel constraints

### Input Schema Pattern

Every tool input includes channel metadata:

```python
from pydantic import BaseModel, Field
from enum import Enum

class Channel(str, Enum):
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"

class ChannelMetadata(BaseModel):
    channel_source: Channel
    customer_id: str
    conversation_id: str | None = None
    thread_id: str | None = None  # Gmail thread continuity

class ToolNameInput(BaseModel):
    """Tool-specific fields + channel metadata."""
    # Tool-specific fields here
    query: str
    # Channel metadata — ALWAYS include
    channel: ChannelMetadata
```

### Output Formatting Per Channel

Tools that produce customer-facing text MUST respect channel limits:

| Channel | Max Length | Style | Signature |
|---------|-----------|-------|-----------|
| Gmail | 500 words | Formal, detailed | "Best regards, TechCorp AI Support Team" |
| WhatsApp | 300 chars preferred, 1600 max | Conversational, concise | None |
| Web Form | 300 words | Semi-formal | "Need more help?" footer |

### Response Adapter Pattern

```python
def adapt_response(raw_response: str, channel: Channel) -> str:
    """Adapt tool output to channel constraints."""
    if channel == Channel.WHATSAPP:
        # Truncate to 300 chars, split if > 1600
        return truncate_and_split(raw_response, preferred=300, max_per_msg=1600)
    elif channel == Channel.GMAIL:
        # Formal wrapper, max 500 words
        return format_email_response(raw_response, max_words=500)
    elif channel == Channel.WEB_FORM:
        # Semi-formal, max 300 words
        return format_web_response(raw_response, max_words=300)
```

## Required Tool Execution Order

The agent MUST call tools in this order. Enforce in tool design:

```
create_ticket → get_customer_history → search_knowledge_base → send_response
```

- `create_ticket` is ALWAYS the first tool call
- `send_response` is ALWAYS the last tool call
- Tools in between can vary but order above is the default flow

## Canonical Tool Definitions

The system requires 5+ MCP tools. Each follows the pattern below:

### 1. `search_knowledge_base`

```python
class KnowledgeSearchInput(BaseModel):
    query: str
    max_results: int = Field(default=5, le=5)
    category: str | None = None
    channel: ChannelMetadata

# Returns: list of relevant doc snippets
# Channel-awareness: result count/verbosity adapts to channel
```

### 2. `create_ticket`

```python
class TicketInput(BaseModel):
    customer_id: str
    issue: str
    priority: str = "medium"  # low | medium | high
    category: str | None = None  # general | technical | billing | feedback | bug_report
    channel: ChannelMetadata

# Returns: ticket_id
# Constraint: MUST be called first in every interaction
```

### 3. `get_customer_history`

```python
class CustomerHistoryInput(BaseModel):
    customer_id: str
    channel: ChannelMetadata

# Returns: last 20 messages across all channels
# Channel-awareness: includes cross-channel context
```

### 4. `escalate_to_human`

```python
class EscalationInput(BaseModel):
    ticket_id: str
    reason: str
    urgency: str = "normal"  # normal | urgent | critical
    channel: ChannelMetadata

# Publishes Kafka event to fte.escalations
# Channel-awareness: includes channel_source for routing
```

### 5. `send_response`

```python
class ResponseInput(BaseModel):
    ticket_id: str
    message: str
    channel: ChannelMetadata

# Constraint: MUST be the last tool call
# Channel-awareness: formats message per channel limits and style
```

## Building a New Tool

Follow this checklist when adding a new MCP tool:

1. **Define input schema** with `ChannelMetadata` included
2. **Implement core logic** — the channel-agnostic business logic
3. **Add channel adaptation** — format output per channel constraints
4. **Register in tool manifest** — add to agent's tool list
5. **Enforce execution order** — document where it fits in the tool chain
6. **Add guardrail checks** — respect agent guardrails (no pricing, no competitor mentions)
7. **Write edge-case tests** — use `test-first-iteration` skill

### Tool Implementation Template

```python
from agents import function_tool

@function_tool
async def tool_name(input: ToolNameInput) -> str:
    """Tool description for the agent.

    Channel-aware: accepts channel_source, formats output per channel.
    """
    # 1. Validate input
    # 2. Execute core logic (channel-agnostic)
    result = await core_logic(input)
    # 3. Adapt response to channel
    return adapt_response(result, input.channel.channel_source)
```

## Must Follow

- [ ] Every tool input schema includes `ChannelMetadata`
- [ ] `create_ticket` is always first, `send_response` is always last
- [ ] Output respects channel length limits (500w email, 300ch WhatsApp, 300w web)
- [ ] Guardrails enforced: no pricing, no competitor mentions, no undocumented features
- [ ] Tool registered in agent tool manifest
- [ ] Pydantic models used for all input/output schemas

## Must Avoid

- Tools that ignore `channel_source` and return uniform responses
- Breaking the tool execution order
- Hardcoding channel-specific logic outside the response adapter
- Tools that access the database without going through `production/database/queries.py`
- Returning raw data without channel-appropriate formatting

## Scaffolding a New Tool

Run the scaffold script to generate a tool file + test stub:

```bash
python scripts/scaffold-tool.py --name check_sentiment --description "Analyze customer message sentiment"
python scripts/scaffold-tool.py --name check_sentiment --description "Analyze sentiment" --output production/agent/tools/
```

Or copy `assets/tool-template.py` as a starting point and fill in the `[PLACEHOLDERS]`.

## Reference Files

| File | When to Read |
|------|--------------|
| `references/tool-patterns.md` | Full implementation examples for all 5 canonical tools, error handling, testing patterns, and anti-patterns to avoid |
| `references/channel-adaptation.md` | Deep dive on response formatting per channel — splitting algorithm, before/after examples, guardrail checks in adapter |
| `scripts/scaffold-tool.py` | Run to generate a new tool file + test stub with all boilerplate pre-filled |
| `assets/tool-template.py` | Copy as starting point for a new tool — has all sections commented and ready to customize |
