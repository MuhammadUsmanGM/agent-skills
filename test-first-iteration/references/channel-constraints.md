# Channel Constraints Reference

Authoritative channel-specific constraints for edge case generation. Use this to ensure every edge case respects the correct limits and behaviors per channel.

---

## Gmail Channel

| Property | Value |
|----------|-------|
| **Handler** | `production/channels/gmail_handler.py` (`GmailHandler`) |
| **Webhook** | `POST /webhooks/gmail` |
| **Inbound** | Gmail API + Google Pub/Sub -> Kafka `fte.tickets.incoming` |
| **Outbound** | Gmail API `send_reply(to_email, subject, body, thread_id)` |
| **Identifier** | Customer email address |

### Response Constraints

| Constraint | Value |
|------------|-------|
| Max length | 500 words |
| Style | Formal, detailed |
| Greeting | "Dear Customer," |
| Signature | "Best regards, TechCorp AI Support Team" |
| Thread continuity | Must preserve `thread_id` for reply threading |

### Parsing Edge Cases

- **HTML-only emails:** Body may contain only HTML, no plain text part. Parser must extract text from HTML.
- **Multipart MIME:** Emails may have text/plain + text/html. Prefer text/plain, fall back to HTML extraction.
- **Forwarded chains:** "---------- Forwarded message ----------" must be parsed; original sender is relevant.
- **Email signatures:** Auto-appended signatures should not trigger keyword detection (e.g., "Attorney at Law" in signature).
- **Attachments:** References to attachments in body but no actual attachment handling (log and note).
- **Missing subject:** Some emails arrive with empty subject. Default to "Support Request".
- **Multiple recipients:** CC/BCC recipients should not receive agent replies.

### Test Data Fields

```json
{
  "channel": "gmail",
  "from_email": "customer@example.com",
  "subject": "Re: Subject Line",
  "body": "Message content",
  "thread_id": "thread_abc123",
  "customer_id": "cust_uuid"
}
```

---

## WhatsApp Channel

| Property | Value |
|----------|-------|
| **Handler** | `production/channels/whatsapp_handler.py` (`WhatsAppHandler`) |
| **Webhook** | `POST /webhooks/whatsapp` |
| **Inbound** | Twilio Webhook -> Kafka `fte.tickets.incoming` |
| **Outbound** | Twilio API `send_message(to_phone, body)` |
| **Identifier** | Customer phone number (WhatsApp format: `whatsapp:+1234567890`) |

### Response Constraints

| Constraint | Value |
|------------|-------|
| Preferred length | 300 characters |
| Max per message | 1600 characters |
| Auto-split | Messages > 1600 chars split into multiple messages |
| Style | Conversational, concise |
| Greeting | None |
| Signature | Reply shortcut hint |

### Specific Behaviors

- **Message splitting:** When response > 1600 chars, split at sentence boundaries, not mid-word.
- **Escalation keywords:** "human", "agent", "representative" trigger immediate escalation.
- **Media messages:** Image-only, voice notes, documents, and location shares. Agent must handle gracefully (acknowledge receipt, ask for text description).
- **Webhook validation:** Validate Twilio signature on every inbound message. Reject invalid signatures.
- **Single-word messages:** "yes", "no", "ok", "thanks" — interpret in conversation context, not as standalone.

### Environment Variables

```
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_NUMBER
```

### Test Data Fields

```json
{
  "channel": "whatsapp",
  "from_phone": "whatsapp:+15551234567",
  "body": "Message content",
  "media_url": null,
  "twilio_signature": "valid_or_invalid",
  "customer_id": "cust_uuid"
}
```

---

## Web Form Channel

| Property | Value |
|----------|-------|
| **Handler** | `production/channels/web_form_handler.py` |
| **Frontend** | `production/web-form/SupportForm.jsx` (React/Next.js) |
| **Submit endpoint** | `POST /support/submit` |
| **Status endpoint** | `GET /support/ticket/{ticket_id}` |
| **Outbound** | API response + email notification |
| **Identifier** | Customer email address (from form) |

### Response Constraints

| Constraint | Value |
|------------|-------|
| Max length | 300 words |
| Style | Semi-formal |
| Greeting | None |
| Footer | "Need more help?" |
| Delivery | API response body + email notification to customer |

### Validation Rules

| Field | Rule | Edge Case |
|-------|------|-----------|
| Name | min 2 characters | "A" (1 char) should fail |
| Email | Valid email format | "not-an-email" should fail |
| Subject | min 5 characters | "Help" (4 chars) should fail |
| Message | min 10 characters | "Fix this" (8 chars) should fail |
| Category | One of: `general`, `technical`, `billing`, `feedback`, `bug_report` | "other" should fail |
| Priority | `low`, `medium`, `high` (default: `medium`) | Missing priority defaults to `medium` |

### Test Data Fields

```json
{
  "channel": "web_form",
  "name": "Customer Name",
  "email": "customer@example.com",
  "subject": "Subject Line Here",
  "category": "general",
  "message": "Detailed message content here",
  "priority": "medium"
}
```

---

## Cross-Channel Constraints

### Shared Guardrails (all channels)

- NEVER discuss competitor products
- NEVER promise features not in documentation
- ALWAYS create ticket before responding
- ALWAYS check sentiment before closing
- NEVER exceed channel-specific length limits

### Shared Escalation Triggers

| Trigger | Threshold | Applies To |
|---------|-----------|------------|
| Legal keywords | "lawyer", "legal", "sue", "attorney" | All channels |
| Negative sentiment | score < 0.3 | All channels |
| Explicit human request | Any phrasing requesting human | All channels |
| WhatsApp-specific keywords | "human", "agent", "representative" | WhatsApp only |
| Failed KB searches | 2 consecutive misses | All channels |
| Pricing/refund inquiries | Any mention | All channels |

### Tool Execution Order (all channels)

```
create_ticket -> get_customer_history -> search_knowledge_base -> send_response
```

- `create_ticket` ALWAYS first
- `send_response` ALWAYS last
- `escalate_to_human` can be inserted before `send_response` when triggered
