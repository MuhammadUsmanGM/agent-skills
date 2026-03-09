# Channel Response Adaptation

Deep dive on formatting agent responses per channel constraints.

---

## Channel Formatting Rules

### Gmail (Email)

| Property | Value |
|----------|-------|
| Style | Formal, detailed |
| Max length | 500 words |
| Greeting | "Dear Customer," |
| Signature | "Best regards,\nTechCorp AI Support Team" |
| Thread continuity | Preserve `thread_id` in every reply |
| Format | Plain text preferred, HTML acceptable |

**Structure:**
```
Dear Customer,

[Body — up to 500 words, formal tone, complete sentences,
proper paragraphs. Address the customer's issue thoroughly.]

Best regards,
TechCorp AI Support Team
```

### WhatsApp

| Property | Value |
|----------|-------|
| Style | Conversational, concise |
| Preferred length | 300 characters |
| Max per message | 1600 characters |
| Auto-split | Split at sentence boundaries if > 1600 chars |
| Greeting | None |
| Quick reply hint | Optional reply shortcut at end |

**Message splitting algorithm:**
1. If response <= 300 chars: send as single message
2. If response 301-1600 chars: send as single message (acceptable)
3. If response > 1600 chars: split at sentence boundaries
   - Find last period/question-mark/exclamation before 1600 char mark
   - Split there, continue with next chunk
   - Each chunk must be <= 1600 chars
   - Never split mid-word or mid-sentence

### Web Form

| Property | Value |
|----------|-------|
| Style | Semi-formal |
| Max length | 300 words |
| Greeting | None |
| Footer | "Need more help? Reply to this email or submit a new request." |
| Delivery | API response body + email notification |

**Structure:**
```
[Body — up to 300 words, semi-formal tone.
Clear and helpful but not as formal as email.]

Need more help? Reply to this email or submit a new request.
```

---

## Response Adapter Implementation

```python
from enum import Enum


class Channel(str, Enum):
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


def adapt_response(raw_response: str, channel: Channel) -> str:
    """Adapt a raw response string to channel-specific constraints."""
    if channel == Channel.GMAIL:
        return _format_gmail(raw_response)
    elif channel == Channel.WHATSAPP:
        return _format_whatsapp(raw_response)
    elif channel == Channel.WEB_FORM:
        return _format_web(raw_response)
    return raw_response


def _format_gmail(text: str) -> str:
    """Format for Gmail: formal, 500 words max, greeting + signature."""
    words = text.split()
    if len(words) > 500:
        text = " ".join(words[:497]) + "..."

    return f"Dear Customer,\n\n{text}\n\nBest regards,\nTechCorp AI Support Team"


def _format_whatsapp(text: str) -> str:
    """Format for WhatsApp: concise, 300 chars preferred, 1600 max per message.

    Returns a single string. For multi-message splitting, use split_whatsapp().
    """
    if len(text) <= 300:
        return text

    if len(text) <= 1600:
        return text

    # Truncate to 1600 for single-message context
    return _truncate_at_sentence(text, 1600)


def split_whatsapp(text: str) -> list[str]:
    """Split long text into multiple WhatsApp messages at sentence boundaries."""
    if len(text) <= 1600:
        return [text]

    messages = []
    remaining = text

    while remaining:
        if len(remaining) <= 1600:
            messages.append(remaining)
            break

        chunk = _truncate_at_sentence(remaining, 1600)
        messages.append(chunk)
        remaining = remaining[len(chunk):].strip()

    return messages


def _format_web(text: str) -> str:
    """Format for Web Form: semi-formal, 300 words max, footer."""
    words = text.split()
    if len(words) > 300:
        text = " ".join(words[:297]) + "..."

    return f"{text}\n\nNeed more help? Reply to this email or submit a new request."


def _truncate_at_sentence(text: str, max_len: int) -> str:
    """Truncate text at the last sentence boundary before max_len."""
    if len(text) <= max_len:
        return text

    truncated = text[:max_len]
    # Find last sentence-ending punctuation
    for i in range(len(truncated) - 1, 0, -1):
        if truncated[i] in ".!?":
            return truncated[: i + 1]

    # No sentence boundary found — truncate at last space
    last_space = truncated.rfind(" ")
    if last_space > 0:
        return truncated[:last_space] + "..."

    return truncated[:max_len]
```

---

## Before/After Examples

### Example 1: Knowledge Base Answer

**Raw response:**
```
The dashboard loading issue is typically caused by browser cache. Clear your browser
cache and cookies, then reload the page. If the issue persists, try a different browser
or disable browser extensions that might interfere with JavaScript execution.
```

**Gmail output:**
```
Dear Customer,

The dashboard loading issue is typically caused by browser cache. Clear your browser
cache and cookies, then reload the page. If the issue persists, try a different browser
or disable browser extensions that might interfere with JavaScript execution.

Best regards,
TechCorp AI Support Team
```

**WhatsApp output:**
```
The dashboard loading issue is usually from browser cache. Clear your cache and cookies, then reload. If it persists, try a different browser or disable extensions.
```

**Web Form output:**
```
The dashboard loading issue is typically caused by browser cache. Clear your browser
cache and cookies, then reload the page. If the issue persists, try a different browser
or disable browser extensions that might interfere with JavaScript execution.

Need more help? Reply to this email or submit a new request.
```

### Example 2: Escalation Acknowledgment

**Raw response:**
```
I understand this is a serious concern. I'm connecting you with a senior support
specialist who can assist you directly. Your ticket reference is #4521. A team member
will be in touch within 2 business hours.
```

**Gmail output:**
```
Dear Customer,

I understand this is a serious concern. I'm connecting you with a senior support
specialist who can assist you directly. Your ticket reference is #4521. A team member
will be in touch within 2 business hours.

Best regards,
TechCorp AI Support Team
```

**WhatsApp output:**
```
I understand this is serious. Connecting you with a specialist now. Your ticket: #4521. Someone will be in touch within 2 hours.
```

**Web Form output:**
```
I understand this is a serious concern. I'm connecting you with a senior support
specialist who can assist you directly. Your ticket reference is #4521. A team member
will be in touch within 2 business hours.

Need more help? Reply to this email or submit a new request.
```

---

## Guardrail Checks in Adaptation

Before sending any response, the adapter should verify:

1. **No pricing info** — scan for dollar signs, "cost", "price", "plan" followed by amounts
2. **No competitor names** — scan against a blocklist
3. **No undocumented features** — only reference KB-sourced content
4. **Length compliance** — hard-enforce channel limits
5. **Tone compliance** — formal for Gmail, conversational for WhatsApp
