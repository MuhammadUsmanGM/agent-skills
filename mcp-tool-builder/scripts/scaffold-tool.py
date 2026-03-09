#!/usr/bin/env python3
"""Scaffold a new channel-aware MCP tool for the Customer Success FTE system.

Usage:
    python scaffold-tool.py --name check_sentiment --description "Analyze customer message sentiment"
    python scaffold-tool.py --name check_sentiment --description "Analyze sentiment" --output production/agent/tools/

Generates a Python file with:
- Pydantic input model with ChannelMetadata
- @function_tool decorated async function
- Channel adaptation boilerplate
- Stub test file
"""

import argparse
import os
import sys
import textwrap


def to_class_name(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in snake.split("_"))


def generate_tool_code(name: str, description: str) -> str:
    class_name = to_class_name(name)
    return textwrap.dedent(f'''\
        """MCP Tool: {name}

        {description}
        Channel-aware: accepts ChannelMetadata, formats output per channel.
        """

        from agents import function_tool
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


        class {class_name}Input(BaseModel):
            """{description}"""
            # TODO: Add tool-specific fields
            query: str = Field(description="Primary input for this tool")
            # Channel metadata — ALWAYS include
            channel: ChannelMetadata


        def adapt_response(raw_response: str, channel: Channel) -> str:
            """Adapt tool output to channel constraints."""
            if channel == Channel.GMAIL:
                # Formal, max 500 words, greeting + signature
                words = raw_response.split()
                if len(words) > 500:
                    raw_response = " ".join(words[:497]) + "..."
                return f"Dear Customer,\\n\\n{{raw_response}}\\n\\nBest regards,\\nTechCorp AI Support Team"
            elif channel == Channel.WHATSAPP:
                # Conversational, 300 chars preferred, 1600 max
                if len(raw_response) > 1600:
                    raw_response = raw_response[:1597] + "..."
                return raw_response
            elif channel == Channel.WEB_FORM:
                # Semi-formal, max 300 words, footer
                words = raw_response.split()
                if len(words) > 300:
                    raw_response = " ".join(words[:297]) + "..."
                return f"{{raw_response}}\\n\\nNeed more help? Reply to this email or submit a new request."
            return raw_response


        @function_tool
        async def {name}(input: {class_name}Input) -> str:
            """{description}

            Channel-aware: accepts channel_source, formats output per channel.
            """
            # 1. Validate input
            # TODO: Add validation logic

            # 2. Execute core logic (channel-agnostic)
            # TODO: Implement core business logic
            result = f"Result for: {{input.query}}"

            # 3. Adapt response to channel
            return adapt_response(result, input.channel.channel_source)
    ''')


def generate_test_code(name: str, description: str) -> str:
    class_name = to_class_name(name)
    return textwrap.dedent(f'''\
        """Tests for MCP Tool: {name}"""

        import pytest
        from unittest.mock import AsyncMock, patch

        # TODO: Update import path to match your project structure
        # from production.agent.tools.{name} import {name}, {class_name}Input, ChannelMetadata, Channel


        class TestChannelMetadata:
            """Verify ChannelMetadata is required and correctly handled."""

            pass  # TODO: Add tests


        class Test{class_name}Gmail:
            """Test {name} with Gmail channel."""

            @pytest.mark.asyncio
            async def test_response_includes_greeting_and_signature(self):
                """Gmail responses must have 'Dear Customer,' and signature."""
                pass  # TODO: Implement

            @pytest.mark.asyncio
            async def test_response_under_500_words(self):
                """Gmail responses must not exceed 500 words."""
                pass  # TODO: Implement


        class Test{class_name}WhatsApp:
            """Test {name} with WhatsApp channel."""

            @pytest.mark.asyncio
            async def test_response_under_300_chars_preferred(self):
                """WhatsApp responses should target 300 chars."""
                pass  # TODO: Implement

            @pytest.mark.asyncio
            async def test_response_split_over_1600_chars(self):
                """WhatsApp responses over 1600 chars must be split."""
                pass  # TODO: Implement


        class Test{class_name}WebForm:
            """Test {name} with Web Form channel."""

            @pytest.mark.asyncio
            async def test_response_includes_footer(self):
                """Web form responses must include 'Need more help?' footer."""
                pass  # TODO: Implement

            @pytest.mark.asyncio
            async def test_response_under_300_words(self):
                """Web form responses must not exceed 300 words."""
                pass  # TODO: Implement


        class Test{class_name}ErrorHandling:
            """Test error scenarios."""

            @pytest.mark.asyncio
            async def test_database_connection_failure(self):
                """Tool should handle DB failures gracefully."""
                pass  # TODO: Implement

            @pytest.mark.asyncio
            async def test_timeout(self):
                """Tool should handle timeouts gracefully."""
                pass  # TODO: Implement
    ''')


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold a new channel-aware MCP tool"
    )
    parser.add_argument("--name", required=True, help="Tool function name (snake_case)")
    parser.add_argument("--description", required=True, help="What the tool does")
    parser.add_argument("--output", default=None, help="Output directory (default: print to stdout)")
    args = parser.parse_args()

    tool_code = generate_tool_code(args.name, args.description)
    test_code = generate_test_code(args.name, args.description)

    if args.output:
        os.makedirs(args.output, exist_ok=True)
        tool_path = os.path.join(args.output, f"{args.name}.py")
        test_path = os.path.join(args.output, f"test_{args.name}.py")

        with open(tool_path, "w", encoding="utf-8") as f:
            f.write(tool_code)
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        print(f"Tool:  {tool_path}")
        print(f"Tests: {test_path}")
    else:
        print("=" * 60)
        print(f"# {args.name}.py")
        print("=" * 60)
        print(tool_code)
        print()
        print("=" * 60)
        print(f"# test_{args.name}.py")
        print("=" * 60)
        print(test_code)


if __name__ == "__main__":
    main()
