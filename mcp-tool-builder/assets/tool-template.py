"""MCP Tool Template: [TOOL_NAME]

[DESCRIPTION]
Channel-aware: accepts ChannelMetadata, formats output per channel.

Usage:
    1. Copy this file to production/agent/tools/[tool_name].py
    2. Replace [PLACEHOLDERS] with actual values
    3. Implement core logic in the function body
    4. Register in the agent's tool manifest
    5. Write tests using the test stub pattern from scripts/scaffold-tool.py
"""

from agents import function_tool
from pydantic import BaseModel, Field
from enum import Enum


# --- Shared types (import from production.agent.models in real code) ---

class Channel(str, Enum):
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class ChannelMetadata(BaseModel):
    """Channel context passed to every tool. ALWAYS include in input schemas."""
    channel_source: Channel
    customer_id: str
    conversation_id: str | None = None
    thread_id: str | None = None  # Gmail thread continuity


# --- Tool Input Schema ---

class ToolNameInput(BaseModel):
    """[DESCRIPTION] - tool input schema."""

    # Tool-specific fields
    query: str = Field(description="Primary input for this tool")
    # Add more fields as needed:
    # max_results: int = Field(default=5, le=10)
    # category: str | None = None

    # Channel metadata — ALWAYS include, never remove
    channel: ChannelMetadata


# --- Channel Response Adapter ---

def adapt_response(raw_response: str, channel: Channel) -> str:
    """Adapt tool output to channel-specific constraints.

    Import from production.agent.formatters in real code.
    """
    if channel == Channel.GMAIL:
        # Formal, max 500 words, greeting + signature
        words = raw_response.split()
        if len(words) > 500:
            raw_response = " ".join(words[:497]) + "..."
        return f"Dear Customer,\n\n{raw_response}\n\nBest regards,\nTechCorp AI Support Team"

    elif channel == Channel.WHATSAPP:
        # Conversational, 300 chars preferred, 1600 max per message
        if len(raw_response) > 1600:
            # Truncate at sentence boundary
            truncated = raw_response[:1600]
            last_period = truncated.rfind(".")
            if last_period > 0:
                return truncated[: last_period + 1]
            return truncated[:1597] + "..."
        return raw_response

    elif channel == Channel.WEB_FORM:
        # Semi-formal, max 300 words, footer
        words = raw_response.split()
        if len(words) > 300:
            raw_response = " ".join(words[:297]) + "..."
        return f"{raw_response}\n\nNeed more help? Reply to this email or submit a new request."

    return raw_response


# --- Tool Implementation ---

@function_tool
async def tool_name(input: ToolNameInput) -> str:
    """[DESCRIPTION]

    Channel-aware: accepts channel_source, formats output per channel.

    Execution order position: [AFTER create_ticket / BEFORE send_response]
    """
    # 1. Validate input
    #    - Check required fields
    #    - Verify customer_id exists (if needed)

    # 2. Execute core logic (channel-agnostic)
    #    - All business logic goes here
    #    - Use production.database.queries for DB access (NEVER direct SQL)
    #    - Example:
    #      from production.database.queries import some_query
    #      result = await some_query(input.query)
    result = f"Result for: {input.query}"

    # 3. Guardrail checks (before responding)
    #    - No pricing information
    #    - No competitor mentions
    #    - No undocumented feature promises

    # 4. Adapt response to channel
    return adapt_response(result, input.channel.channel_source)
