---
name: test-first-iteration
description: |
  Generate comprehensive edge-case test files before implementing features, enforcing
  test-first development for the Customer Success FTE system. This skill should be used
  when building or iterating on channel handlers (Gmail, WhatsApp, Web Form), agent tools,
  or message processing — to produce tests/edge-cases-{channel}.json files with 20+ edge
  cases per channel BEFORE any implementation code is written.
---

# Test-First Iteration

Enforce test-first development by generating edge-case test files before implementation.

## Core Rule

**Never write implementation code until the edge-case test file exists and is reviewed.**

```
1. Identify feature scope and affected channels
2. Generate tests/edge-cases-{channel}.json (20+ cases per channel)
3. User reviews edge cases
4. THEN implement feature code
5. Validate implementation against edge cases
```

## Before Generating Tests

Gather context to ensure comprehensive coverage:

| Source | Gather |
|--------|--------|
| **Codebase** | Existing tests, channel handlers, agent tools, schema |
| **Conversation** | Feature being built, user's specific requirements |
| **AGENTS.md** | Channel constraints, guardrails, escalation triggers |
| **Skill References** | Edge case patterns from `references/edge-case-patterns.md` |

## Edge Case File Format

Each `tests/edge-cases-{channel}.json` follows this structure:

```json
{
  "channel": "gmail|whatsapp|web_form",
  "feature": "feature-name",
  "generated": "YYYY-MM-DD",
  "edge_cases": [
    {
      "id": "EC-{CHANNEL}-{NNN}",
      "category": "category-name",
      "description": "What this tests",
      "input": { },
      "expected_behavior": "What should happen",
      "expected_output": { },
      "severity": "critical|high|medium|low",
      "tags": ["escalation", "sentiment", "formatting"]
    }
  ]
}
```

## Required Edge Case Categories

Generate at least 20 edge cases per channel, covering ALL of these categories:

### Universal Categories (all channels)

| Category | Examples |
|----------|----------|
| **Escalation triggers** | Legal keywords ("lawyer", "sue"), sentiment < 0.3, explicit human request |
| **Guardrail violations** | Competitor mentions, pricing questions, undocumented feature promises |
| **Sentiment extremes** | Profanity, all-caps rage, passive-aggressive, sarcasm |
| **Empty/malformed input** | Blank message, only whitespace, only emojis, only URLs |
| **Injection attempts** | Prompt injection, SQL injection in message body, XSS payloads |
| **Multi-language** | Non-English messages, mixed-language, RTL text |
| **Customer identity** | Unknown customer, cross-channel customer, merged accounts |
| **Tool execution order** | Missing ticket creation, out-of-order tool calls |
| **Knowledge base misses** | No results found, ambiguous query, 2+ failed searches |

### Channel-Specific Categories

#### Gmail (`tests/edge-cases-gmail.json`)
| Category | Examples |
|----------|----------|
| **Thread continuity** | Reply to closed ticket, orphaned thread_id, missing thread |
| **Email parsing** | HTML-only body, multipart MIME, forwarded chains, signatures |
| **Length limits** | Response exceeding 500 words, email with huge attachment reference |
| **Formatting** | Missing subject, multiple recipients, CC/BCC handling |

#### WhatsApp (`tests/edge-cases-whatsapp.json`)
| Category | Examples |
|----------|----------|
| **Message splitting** | Response > 1600 chars, response > 300 chars preferred limit |
| **Media messages** | Image-only, voice note, document, location share |
| **Webhook validation** | Invalid Twilio signature, replay attack, malformed payload |
| **Quick replies** | Single-word responses ("yes", "no", "ok"), keyword triggers ("human", "agent") |

#### Web Form (`tests/edge-cases-web_form.json`)
| Category | Examples |
|----------|----------|
| **Validation boundaries** | Name=1 char, subject=4 chars, message=9 chars (below min) |
| **Category values** | Invalid category, missing category, empty string |
| **Priority edge cases** | Missing priority (should default medium), invalid priority value |
| **Duplicate submissions** | Same content submitted twice rapidly, same email different names |

## Workflow

### Step 1: Identify Scope

Determine which channels and components the feature touches:

```
Feature: "Add refund request handling"
→ Channels affected: gmail, whatsapp, web_form
→ Components: agent tools, escalation logic, ticket creation
→ Generate: 3 edge-case files
```

### Step 2: Generate Edge Cases

For each affected channel, create `tests/edge-cases-{channel}.json` with 20+ cases. Assign severity:

| Severity | Criteria |
|----------|----------|
| **critical** | Data loss, security breach, wrong customer, missed escalation |
| **high** | Guardrail bypass, wrong channel formatting, broken thread |
| **medium** | Suboptimal response, minor formatting issue |
| **low** | Cosmetic, non-functional edge case |

### Step 3: Review with User

Present a summary table:

```
Channel: gmail — 22 edge cases
  critical: 4 | high: 7 | medium: 8 | low: 3

Channel: whatsapp — 24 edge cases
  critical: 5 | high: 8 | medium: 7 | low: 4
```

Ask: "Review these edge cases. Add, remove, or adjust any before implementation?"

### Step 4: Implement Against Tests

Only after edge cases are approved, begin implementation. Reference edge case IDs in code comments where relevant.

### Step 5: Validate

After implementation, walk through each edge case and verify behavior matches `expected_behavior`. Report pass/fail per case.

## Must Follow

- [ ] Generate test files BEFORE any implementation code
- [ ] Minimum 20 edge cases per affected channel
- [ ] Cover ALL required categories listed above
- [ ] Include at least 3 critical-severity cases per channel
- [ ] Every edge case has a unique ID following `EC-{CHANNEL}-{NNN}` format
- [ ] User reviews edge cases before implementation begins

## Must Avoid

- Writing implementation code before edge-case files exist
- Generating fewer than 20 edge cases per channel
- Skipping security-related edge cases (injection, escalation bypass)
- Creating vague expected_behavior ("should work correctly")
- Duplicating edge cases across channels without channel-specific context

## Generating Edge Cases with Script

Run the generator script to scaffold a starter edge-case file with 20+ cases:

```bash
python scripts/generate-edge-cases.py --channel gmail --feature "feature-name" --output tests/
python scripts/generate-edge-cases.py --channel whatsapp --feature "feature-name" --output tests/
python scripts/generate-edge-cases.py --channel web_form --feature "feature-name" --output tests/
```

The script generates `tests/edge-cases-{channel}.json` pre-populated with universal + channel-specific cases. Review and customize the `[TODO]` input placeholders for your feature.

## Template

Copy `assets/edge-case-template.json` for the expected file structure with example entries at all severity levels.

## Reference Files

| File | When to Read |
|------|--------------|
| `references/edge-case-patterns.md` | Detailed patterns per category with concrete examples, good/bad edge case templates, and per-channel input examples |
| `references/channel-constraints.md` | Channel-specific limits, formatting rules, validation rules, escalation keywords, and test data field schemas |
| `scripts/generate-edge-cases.py` | Run to scaffold a starter edge-case file with 20+ cases for a given channel |
| `assets/edge-case-template.json` | Copy as starting point for manually creating edge-case files |
