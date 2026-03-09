# Prompt Format Templates

Three formats. Pick the right one for the use case.

---

## Format 1: Chat Interface Prompt (Plain)

Use for: conversational assistants, expert personas, behavioral prompts
Audience: people copy-pasting into Claude.ai, ChatGPT, etc.
Rule: No XML tags. Plain prose + numbered rules.

```
You are a [specific role with relevant background].

Your job is to [core task in one sentence].

Core rules:
1. [Most important behavioral rule]
2. [Second rule]
3. [Edge case handling — what to do when context is missing]
4. [What NOT to do]
5. [Output style / tone]

Before advising on [topic], always ask: [the 1-2 pieces of context you need].
```

**Example:**
```
You are a senior B2B sales strategist who has personally closed $10M+ in deals.

Your job is to help founders and sales teams close more deals faster with better unit economics.

Core rules:
1. Before advising on any deal, ask for: ACV, sales cycle length, buyer role, and current stage.
2. Qualify every opportunity through MEDDIC. If any element is unknown, that's the next task — not pitching.
3. When a deal is stalled, diagnose before advising. Stalls have three causes: no champion, no urgency, wrong buyer.
4. Never recommend sending a proposal before verbal alignment on the decision.
5. Be direct. If the deal is dead, say so.
```

---

## Format 2: Developer / Agent Prompt (Structured XML)

Use for: API integrations, automated pipelines, structured output tasks
Audience: developers building products on top of LLMs
Rule: XML tags for distinct sections. Output format must be explicit.

```xml
You are a [role].

<context>
[Background the model needs to do the job. Not instructions — context.]
</context>

<instructions>
1. [Instruction 1]
2. [Instruction 2]
3. [Edge case handling]
</instructions>

<examples>
<example>
<input>[Sample input]</input>
<output>[Expected output — exact format]</output>
</example>
</examples>

<output_format>
[Exact format specification. If JSON, show the schema. If structured text, show the template.]
</output_format>
```

---

## Format 3: Hybrid (Plain Rules + Structured Examples)

Use for: expert personas that also need to produce structured outputs
Audience: mixed — both chat users and developers
Rule: Plain prose for role + rules. XML only for the example block.

```
You are a [role].

Your job is to [core task].

Core rules:
1. [Rule 1]
2. [Rule 2]
3. [Rule 3]

**Example**

User: [realistic input]

Response:
[Exactly how the model should respond — format, tone, structure, what it asks vs. what it answers directly]
```

---

## Choosing the Right Format

| Signal | Format |
|---|---|
| User will paste into chat UI | Plain (Format 1) |
| Output will be parsed by code | XML (Format 2) |
| Expert persona + specific output structure | Hybrid (Format 3) |
| Prompt is under 150 words | Plain (Format 1) always |
| Multiple structured input types | XML (Format 2) |