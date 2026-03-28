# Workflow: /reply — Reply to Email or Message

## Objective
Summarize an existing email thread and draft a reply in the user's voice. Always a draft — never sent automatically.

## Trigger
`/reply [thread context]`

Context can be: a subject line, a sender name, a forwarded message, or a thread ID.

## Required Inputs
- Thread identifier (from the command)
- `gmail` MCP — to fetch the actual thread
- `context/personal.md` — voice, tone, key relationships

## Steps

1. **Identify the thread** — Use the `gmail` MCP to find and fetch the thread based on the context provided.
   - If multiple threads match, list them and ask the user to confirm which one.

2. **Summarize the thread** — In exactly 2 sentences: what was asked/said, and what is expected from the user.

3. **Flag issues** — Before drafting, check and surface any of:
   - Thread waiting > 48h without a reply from the user
   - An unfulfilled commitment the user made in a prior message in this thread
   - Sender is a key relationship (investor, customer, co-founder, advisor)

4. **Load voice rules** — Read tone and forbidden phrases from `context/personal.md`.

5. **Draft the reply** — Match the register of the original thread. Get to the point in the first sentence.

6. **For high-stakes threads** (investor, key customer, legal): provide two versions:
   - Version A: Assertive
   - Version B: Diplomatic

## Output Format

**Thread summary:** [2 sentences — what was said, what's expected]

⚠️ **Flags:** [Any of: overdue > 48h / unfulfilled commitment / key relationship]

---

**DRAFT REPLY**

**To:** [Sender]
**Subject:** Re: [Original subject]

[Body]

[Signature]

---
*[High-stakes only: Version A and Version B]*

## Hard Rules
- NEVER call gmail send. Draft only.
- NEVER fabricate thread content — only draft based on what was actually fetched.
- If thread cannot be found, say so clearly and ask for more details.
- NEVER quote a Telegram message inside an email reply without asking the user first.

## Edge Cases
- **Thread not found**: Ask the user to forward the email or provide more identifying details
- **Very long thread (10+ messages)**: Summarize the last 3–4 messages only; note that earlier context was skipped
- **Thread has multiple recipients**: Flag this — the reply may need to be addressed carefully
- **User has already replied**: Note it and ask if they want to send a follow-up anyway
