#!/usr/bin/env python3
"""Generate edge-case test files for Customer Success FTE channels.

Usage:
    python generate-edge-cases.py --channel gmail --feature "refund-handling" --output tests/
    python generate-edge-cases.py --channel whatsapp --feature "sentiment-detection" --output tests/
    python generate-edge-cases.py --channel web_form --feature "form-validation" --output tests/

Generates tests/edge-cases-{channel}.json with 20+ edge cases per channel.
"""

import argparse
import json
import os
import sys
from datetime import date

# --- Universal edge cases (apply to all channels) ---

UNIVERSAL_CASES = [
    {
        "category": "escalation_triggers",
        "description": "Customer threatens legal action with keyword 'lawyer'",
        "expected_behavior": "Detect 'lawyer' keyword, trigger escalation via escalate_to_human with reason='legal_mention', set ticket priority to high",
        "severity": "critical",
        "tags": ["escalation", "legal"],
    },
    {
        "category": "escalation_triggers",
        "description": "Customer uses keyword 'sue' embedded in longer sentence",
        "expected_behavior": "Detect 'sue' keyword even when not standalone, trigger escalation",
        "severity": "critical",
        "tags": ["escalation", "legal"],
    },
    {
        "category": "escalation_triggers",
        "description": "Sentiment score below 0.3 due to profane language",
        "expected_behavior": "Sentiment analysis returns score < 0.3, trigger escalation with reason='negative_sentiment'",
        "severity": "critical",
        "tags": ["escalation", "sentiment"],
    },
    {
        "category": "escalation_triggers",
        "description": "Customer explicitly requests to speak with a human",
        "expected_behavior": "Detect human request intent, trigger immediate escalation",
        "severity": "critical",
        "tags": ["escalation", "human-request"],
    },
    {
        "category": "escalation_triggers",
        "description": "Knowledge base returns zero results on two consecutive searches",
        "expected_behavior": "After 2 failed searches, escalate with reason='knowledge_gap'",
        "severity": "high",
        "tags": ["escalation", "knowledge-base"],
    },
    {
        "category": "escalation_triggers",
        "description": "Customer asks about pricing or requests a refund",
        "expected_behavior": "Detect pricing/refund intent, escalate immediately without discussing pricing",
        "severity": "critical",
        "tags": ["escalation", "pricing"],
    },
    {
        "category": "guardrail_violations",
        "description": "Customer asks to compare product with a named competitor",
        "expected_behavior": "Deflect competitor discussion, redirect to own product features without naming competitor",
        "severity": "high",
        "tags": ["guardrail", "competitor"],
    },
    {
        "category": "guardrail_violations",
        "description": "Customer asks about an undocumented feature on the roadmap",
        "expected_behavior": "Do not confirm or deny unreleased features, offer to log as feedback",
        "severity": "high",
        "tags": ["guardrail", "feature-promise"],
    },
    {
        "category": "sentiment_extremes",
        "description": "Message contains all-caps rage text",
        "expected_behavior": "Detect negative sentiment from all-caps pattern, score < 0.3, escalate",
        "severity": "high",
        "tags": ["sentiment", "formatting"],
    },
    {
        "category": "sentiment_extremes",
        "description": "Sarcastic positive-sounding message with negative intent",
        "expected_behavior": "Detect sarcasm, do not misclassify as positive sentiment",
        "severity": "medium",
        "tags": ["sentiment", "sarcasm"],
    },
    {
        "category": "empty_malformed_input",
        "description": "Message body is completely empty or whitespace only",
        "expected_behavior": "Handle gracefully, ask customer to provide details. Still create ticket.",
        "severity": "medium",
        "tags": ["input-validation", "empty"],
    },
    {
        "category": "empty_malformed_input",
        "description": "Message contains only emojis with no text",
        "expected_behavior": "Attempt sentiment inference from emojis, ask for clarification",
        "severity": "low",
        "tags": ["input-validation", "emoji"],
    },
    {
        "category": "injection_attempts",
        "description": "Prompt injection attempting to override system instructions",
        "expected_behavior": "Ignore injection payload, respond to legitimate content or ask for clarification",
        "severity": "critical",
        "tags": ["security", "prompt-injection"],
    },
    {
        "category": "injection_attempts",
        "description": "SQL injection payload in message body",
        "expected_behavior": "Treat as literal text, parameterized queries prevent execution",
        "severity": "critical",
        "tags": ["security", "sql-injection"],
    },
    {
        "category": "multi_language",
        "description": "Message entirely in non-English language (Spanish)",
        "expected_behavior": "Detect language, respond in same language or acknowledge in English",
        "severity": "medium",
        "tags": ["language", "non-english"],
    },
    {
        "category": "customer_identity",
        "description": "Customer contacts from a new channel not yet in customer_identifiers",
        "expected_behavior": "Create new identifier record, link to existing customer if match found, merge history",
        "severity": "high",
        "tags": ["identity", "cross-channel"],
    },
    {
        "category": "tool_execution_order",
        "description": "Agent attempts to call send_response before create_ticket",
        "expected_behavior": "Block execution, enforce create_ticket as mandatory first step",
        "severity": "critical",
        "tags": ["tool-order", "enforcement"],
    },
    {
        "category": "knowledge_base_misses",
        "description": "Customer pastes a large error log as their message",
        "expected_behavior": "Extract key terms from error log, search knowledge base with summarized query",
        "severity": "medium",
        "tags": ["knowledge-base", "long-input"],
    },
]

# --- Channel-specific edge cases ---

GMAIL_SPECIFIC = [
    {
        "category": "thread_continuity",
        "description": "Reply to a previously resolved/closed ticket thread",
        "input": {
            "channel": "gmail",
            "from_email": "returning.customer@example.com",
            "subject": "Re: Resolved - Order #1234",
            "body": "Actually, the issue came back. Same problem as before.",
            "thread_id": "thread_resolved_001",
        },
        "expected_behavior": "Detect existing thread_id, reopen or create new ticket linked to previous conversation, preserve thread continuity in reply",
        "severity": "high",
        "tags": ["thread", "reopen"],
    },
    {
        "category": "email_parsing",
        "description": "Email with HTML-only body, no plain text part",
        "input": {
            "channel": "gmail",
            "from_email": "html.sender@example.com",
            "subject": "Help needed",
            "body": "<html><body><p>I need help with <b>my account</b>. The <a href='#'>dashboard</a> is not loading.</p></body></html>",
            "thread_id": "thread_html_001",
        },
        "expected_behavior": "Parse HTML body to extract plain text: 'I need help with my account. The dashboard is not loading.' Process as normal text message.",
        "severity": "medium",
        "tags": ["parsing", "html"],
    },
    {
        "category": "email_parsing",
        "description": "Forwarded email chain with nested content",
        "input": {
            "channel": "gmail",
            "from_email": "forwarder@example.com",
            "subject": "Fwd: Original Issue",
            "body": "Please see below.\n\n---------- Forwarded message ----------\nFrom: original.sender@example.com\nDate: Mon, Jan 1, 2026\nSubject: Original Issue\n\nI can't access my account since the update.",
            "thread_id": None,
        },
        "expected_behavior": "Parse forwarded chain, extract original message content, create new thread (no existing thread_id)",
        "severity": "medium",
        "tags": ["parsing", "forwarded"],
    },
    {
        "category": "length_limits",
        "description": "Agent generates response exceeding 500-word email limit",
        "input": {
            "channel": "gmail",
            "from_email": "detailed.asker@example.com",
            "subject": "Multiple questions about all features",
            "body": "Can you explain every feature of your platform in detail? I want to know about analytics, integrations, API, billing, team management, and security features.",
            "thread_id": "thread_long_001",
        },
        "expected_behavior": "Response must be truncated or summarized to stay under 500 words. Include 'Dear Customer,' greeting and 'Best regards, TechCorp AI Support Team' signature within the limit.",
        "severity": "high",
        "tags": ["formatting", "length-limit"],
    },
    {
        "category": "formatting",
        "description": "Inbound email with missing subject line",
        "input": {
            "channel": "gmail",
            "from_email": "no.subject@example.com",
            "subject": "",
            "body": "I need help urgently.",
            "thread_id": None,
        },
        "expected_behavior": "Default subject to 'Support Request', create ticket normally, reply with subject 'Re: Support Request'",
        "severity": "medium",
        "tags": ["formatting", "missing-field"],
    },
]

WHATSAPP_SPECIFIC = [
    {
        "category": "message_splitting",
        "description": "Agent response exceeds 1600 character WhatsApp limit",
        "input": {
            "channel": "whatsapp",
            "from_phone": "whatsapp:+15551234567",
            "body": "Explain everything about your API integration options",
        },
        "expected_behavior": "Split response at sentence boundaries into multiple messages, each <= 1600 chars. Preferred target is 300 chars per message.",
        "severity": "high",
        "tags": ["formatting", "splitting"],
    },
    {
        "category": "media_messages",
        "description": "Customer sends image-only message with no text",
        "input": {
            "channel": "whatsapp",
            "from_phone": "whatsapp:+15559876543",
            "body": "",
            "media_url": "https://api.twilio.com/media/IMG001.jpg",
        },
        "expected_behavior": "Acknowledge image receipt, ask customer to describe their issue in text. Create ticket noting media attachment.",
        "severity": "medium",
        "tags": ["media", "image"],
    },
    {
        "category": "webhook_validation",
        "description": "Inbound message with invalid Twilio webhook signature",
        "input": {
            "channel": "whatsapp",
            "from_phone": "whatsapp:+15550000000",
            "body": "This is a spoofed message",
            "twilio_signature": "invalid_signature_abc123",
        },
        "expected_behavior": "Reject message at webhook handler level, return 403, do not process or create ticket",
        "severity": "critical",
        "tags": ["security", "webhook"],
    },
    {
        "category": "quick_replies",
        "description": "Customer sends single word 'human' triggering escalation",
        "input": {
            "channel": "whatsapp",
            "from_phone": "whatsapp:+15551112222",
            "body": "human",
        },
        "expected_behavior": "Detect WhatsApp-specific escalation keyword 'human', trigger immediate escalation to human agent",
        "severity": "critical",
        "tags": ["escalation", "keyword"],
    },
    {
        "category": "quick_replies",
        "description": "Customer replies with just 'ok' to a previous agent message",
        "input": {
            "channel": "whatsapp",
            "from_phone": "whatsapp:+15553334444",
            "body": "ok",
        },
        "expected_behavior": "Interpret in conversation context — if previous message asked for confirmation, treat as positive. Do not create new ticket if conversation is active.",
        "severity": "low",
        "tags": ["context", "single-word"],
    },
    {
        "category": "message_splitting",
        "description": "Response with multi-byte characters (CJK) near the 300 char limit",
        "input": {
            "channel": "whatsapp",
            "from_phone": "whatsapp:+81901234567",
            "body": "アカウントの問題があります",
        },
        "expected_behavior": "Count characters (not bytes) for the 300-char preferred limit. CJK characters count as 1 character each.",
        "severity": "medium",
        "tags": ["language", "character-counting"],
    },
]

WEB_FORM_SPECIFIC = [
    {
        "category": "validation_boundaries",
        "description": "Name field with only 1 character (below minimum 2)",
        "input": {
            "channel": "web_form",
            "name": "A",
            "email": "valid@example.com",
            "subject": "Valid Subject",
            "message": "This is a valid message that is long enough.",
            "category": "general",
            "priority": "medium",
        },
        "expected_behavior": "Reject submission with validation error: 'Name must be at least 2 characters'",
        "severity": "medium",
        "tags": ["validation", "name"],
    },
    {
        "category": "validation_boundaries",
        "description": "Subject with exactly 4 characters (below minimum 5)",
        "input": {
            "channel": "web_form",
            "name": "John",
            "email": "john@example.com",
            "subject": "Help",
            "message": "This is a valid message that is long enough.",
            "category": "technical",
            "priority": "high",
        },
        "expected_behavior": "Reject submission with validation error: 'Subject must be at least 5 characters'",
        "severity": "medium",
        "tags": ["validation", "subject"],
    },
    {
        "category": "validation_boundaries",
        "description": "Message with exactly 9 characters (below minimum 10)",
        "input": {
            "channel": "web_form",
            "name": "Jane Doe",
            "email": "jane@example.com",
            "subject": "Account issue",
            "message": "Fix this!",
            "category": "general",
            "priority": "low",
        },
        "expected_behavior": "Reject submission with validation error: 'Message must be at least 10 characters'",
        "severity": "medium",
        "tags": ["validation", "message"],
    },
    {
        "category": "category_values",
        "description": "Submission with invalid category value",
        "input": {
            "channel": "web_form",
            "name": "Test User",
            "email": "test@example.com",
            "subject": "Some issue here",
            "message": "I have a problem with my account that needs fixing.",
            "category": "other",
            "priority": "medium",
        },
        "expected_behavior": "Reject with error: 'Category must be one of: general, technical, billing, feedback, bug_report'",
        "severity": "medium",
        "tags": ["validation", "category"],
    },
    {
        "category": "priority_edge_cases",
        "description": "Submission with missing priority field (should default to medium)",
        "input": {
            "channel": "web_form",
            "name": "Default User",
            "email": "default@example.com",
            "subject": "Missing priority test",
            "message": "Submitted without selecting a priority level.",
            "category": "general",
        },
        "expected_behavior": "Accept submission, default priority to 'medium', create ticket normally",
        "severity": "low",
        "tags": ["defaults", "priority"],
    },
    {
        "category": "duplicate_submissions",
        "description": "Same form content submitted twice within 5 seconds",
        "input": {
            "channel": "web_form",
            "name": "Double Clicker",
            "email": "double@example.com",
            "subject": "Duplicate test submission",
            "message": "This message was accidentally submitted twice.",
            "category": "general",
            "priority": "medium",
        },
        "expected_behavior": "Detect duplicate within time window, return existing ticket_id instead of creating a second ticket",
        "severity": "high",
        "tags": ["dedup", "double-submit"],
    },
    {
        "category": "injection_attempts",
        "description": "XSS payload in the name field of web form",
        "input": {
            "channel": "web_form",
            "name": "<script>alert('xss')</script>",
            "email": "xss@example.com",
            "subject": "Normal subject line",
            "message": "Normal message content with no malicious intent.",
            "category": "general",
            "priority": "low",
        },
        "expected_behavior": "Sanitize name field, strip HTML tags. Store sanitized version. Never render raw HTML from user input.",
        "severity": "critical",
        "tags": ["security", "xss"],
    },
]


def build_channel_cases(channel: str, feature: str) -> list[dict]:
    """Build edge cases for a specific channel."""
    cases = []
    counter = 1

    channel_prefix = channel.upper().replace("_", "-")

    # Add universal cases with channel-specific input
    for uc in UNIVERSAL_CASES:
        case = {
            "id": f"EC-{channel_prefix}-{counter:03d}",
            "category": uc["category"],
            "description": uc["description"],
            "input": build_input(channel, uc["description"]),
            "expected_behavior": uc["expected_behavior"],
            "expected_output": {},
            "severity": uc["severity"],
            "tags": uc["tags"],
        }
        cases.append(case)
        counter += 1

    # Add channel-specific cases
    specific = {
        "gmail": GMAIL_SPECIFIC,
        "whatsapp": WHATSAPP_SPECIFIC,
        "web_form": WEB_FORM_SPECIFIC,
    }

    for sc in specific.get(channel, []):
        case = {
            "id": f"EC-{channel_prefix}-{counter:03d}",
            "category": sc["category"],
            "description": sc["description"],
            "input": sc.get("input", build_input(channel, sc["description"])),
            "expected_behavior": sc["expected_behavior"],
            "expected_output": {},
            "severity": sc["severity"],
            "tags": sc["tags"],
        }
        cases.append(case)
        counter += 1

    return cases


def build_input(channel: str, description: str) -> dict:
    """Build a placeholder input object for universal cases per channel."""
    base_message = f"[TODO: Write realistic input for: {description}]"

    if channel == "gmail":
        return {
            "channel": "gmail",
            "from_email": "customer@example.com",
            "subject": "Support Request",
            "body": base_message,
            "thread_id": "thread_placeholder",
            "customer_id": "cust_placeholder",
        }
    elif channel == "whatsapp":
        return {
            "channel": "whatsapp",
            "from_phone": "whatsapp:+15551234567",
            "body": base_message,
            "customer_id": "cust_placeholder",
        }
    elif channel == "web_form":
        return {
            "channel": "web_form",
            "name": "Test Customer",
            "email": "test@example.com",
            "subject": "Support Request",
            "message": base_message,
            "category": "general",
            "priority": "medium",
        }
    return {"channel": channel, "message": base_message}


def main():
    parser = argparse.ArgumentParser(
        description="Generate edge-case test files for Customer Success FTE channels"
    )
    parser.add_argument(
        "--channel",
        required=True,
        choices=["gmail", "whatsapp", "web_form"],
        help="Target channel",
    )
    parser.add_argument(
        "--feature",
        required=True,
        help="Feature name being tested",
    )
    parser.add_argument(
        "--output",
        default="tests/",
        help="Output directory (default: tests/)",
    )
    args = parser.parse_args()

    cases = build_channel_cases(args.channel, args.feature)

    output = {
        "channel": args.channel,
        "feature": args.feature,
        "generated": date.today().isoformat(),
        "total_cases": len(cases),
        "severity_summary": {
            "critical": sum(1 for c in cases if c["severity"] == "critical"),
            "high": sum(1 for c in cases if c["severity"] == "high"),
            "medium": sum(1 for c in cases if c["severity"] == "medium"),
            "low": sum(1 for c in cases if c["severity"] == "low"),
        },
        "edge_cases": cases,
    }

    os.makedirs(args.output, exist_ok=True)
    filepath = os.path.join(args.output, f"edge-cases-{args.channel}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(cases)} edge cases for {args.channel}")
    print(f"  critical: {output['severity_summary']['critical']}")
    print(f"  high:     {output['severity_summary']['high']}")
    print(f"  medium:   {output['severity_summary']['medium']}")
    print(f"  low:      {output['severity_summary']['low']}")
    print(f"Output: {filepath}")


if __name__ == "__main__":
    main()
