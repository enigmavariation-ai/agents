# Workflow: /email — Draft an Outbound Email

## Objective
Draft an email in the user's voice. Always a draft — never sent automatically.

## Trigger
`/email [context]`

Context can be: a recipient name, a topic, a forwarded thread, or a rough intent ("email to investor about our Series A timeline").

## Required Inputs
- User's context/intent (from the command)
- `context/personal.md` — tone, signature, key relationships, things never to say

## Steps

1. **Parse intent** — Extract: recipient, purpose, tone needed (assertive/diplomatic/neutral), any urgency signal.
   - If intent is ambiguous, ask ONE clarifying question before drafting. Don't guess and produce something wrong.

2. **Load communication style** — Read tone rules, signature, and forbidden phrases from `context/personal.md`.

3. **Check relationship context** — If the recipient matches someone in key customers, investors, advisors, or co-founders, note this — it affects tone.

4. **Draft the email** — Follow voice rules: direct, warm, no openers like "I hope this finds you well."

5. **For high-stakes emails** (investor, key customer, legal matter): produce two versions:
   - Version A: Assertive
   - Version B: Diplomatic

6. **Present the draft** — Show subject line + body. Label clearly as DRAFT.

## Output Format

**DRAFT**

**To:** [Recipient]
**Subject:** [Subject line]

[Body]

[Signature from context/personal.md]

---
*[For high-stakes: repeat above with "Version A — Assertive" and "Version B — Diplomatic" labels]*

## Voice Rules
- No: "I hope this finds you well", "As per my last email", "Please don't hesitate to reach out", "I wanted to follow up", "Circling back"
- Yes: Get to the point in the first sentence. Warm but efficient. Sign off simply.
- Match formality to the relationship — casual with co-founders, professional with investors, direct with customers

## Hard Rules
- NEVER call gmail send or any send function. Draft only.
- NEVER include personal contact details in any web search done to research the recipient.
- If recipient is unknown and the intent is ambiguous, ask before drafting.

## Edge Cases
- **No recipient specified**: Ask who it's going to before drafting
- **Sensitive content (legal, HR, financial)**: Flag it and suggest the user review carefully before sending
- **Reply vs. new email confusion**: If this looks like a reply to an existing thread, redirect to `/reply` workflow
