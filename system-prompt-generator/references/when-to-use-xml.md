# When to Use XML Tags

A decision guide. Be honest about whether XML is adding value or just adding ceremony.

---

## Use XML Tags When

**1. The prompt has 3+ functionally distinct sections**
If context, instructions, and output format each need to be interpreted differently by the model, tags help it treat them differently.

Good:
```xml
<context>
You are reviewing a legal contract for a SaaS company.
</context>

<instructions>
1. Flag clauses that limit liability
2. Identify auto-renewal terms
</instructions>

<output_format>
Return a JSON array of flagged clauses with: clause_text, risk_level (HIGH/MEDIUM/LOW), explanation.
</output_format>
```

**2. User input is embedded in the prompt**
Always wrap dynamic user content in tags to prevent prompt injection and help the model distinguish instructions from data.

```xml
Review the following document and extract all action items.

<document>
{{user_document}}
</document>
```

**3. Output will be parsed programmatically**
When code downstream needs to extract specific fields, structure the output format with tags or JSON schema inside `<output_format>`.

**4. You have multiple examples to separate**
```xml
<examples>
<example>
<input>Invoice #1042, $500, due 2024-03-15</input>
<o>{"invoice_id": "1042", "amount": 500, "due_date": "2024-03-15"}</o>
</example>
<example>
<input>Bill for $1,200 - Project Alpha</input>
<o>{"invoice_id": null, "amount": 1200, "due_date": null, "project": "Alpha"}</o>
</example>
</examples>
```

---

## Skip XML Tags When

**1. The prompt is a set of behavioral rules**
A numbered list is cleaner and more readable for chat interface prompts.

Bad:
```xml
<instructions>
1. Be direct
2. Don't sugarcoat feedback
</instructions>
```

Good:
```
Core rules:
1. Be direct.
2. Don't sugarcoat feedback.
```

**2. The prompt is under 150 words**
Short prompts don't have enough sections to justify the structural overhead.

**3. The audience is copy-pasting into a chat interface**
XML tags look technical and intimidating to non-developer users. They also add noise when the model is in a conversational context.

**4. There's only one of each section**
Wrapping a single paragraph in `<context>` tags doesn't help the model — it just adds visual noise.

---

## The Honest Test

Before adding XML tags, ask: "Does this tag tell the model to treat this section differently than it would without the tag?"

If the answer is no — skip it.