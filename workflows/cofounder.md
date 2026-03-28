# Workflow: /cofounder — Daily Co-Founder Update

## Objective
Draft a concise daily sync message to both co-founders. Under 200 words. Direct, warm, startup-casual.

## Trigger
`/cofounder` (also called automatically by `/morning`)

## Required Inputs
- `context/personal.md` — co-founder names, next shared calendar slot
- Gmail MCP — sent emails from yesterday afternoon/evening (to identify "Done" items)
- Gmail MCP — open threads the user is driving (to identify "In progress" items)
- gcal MCP — next shared calendar event with co-founders

## Steps

1. **Load context** — Read co-founder names and communication style from `context/personal.md`.

2. **Fetch sent mail** — Use `gmail` MCP to get emails sent after 12:00 yesterday. These are "Done" candidates.

3. **Fetch open threads** — Use `gmail` MCP to get threads where the user sent the last message and is waiting on a reply, or threads the user needs to action. These are "In progress" candidates.

4. **Check shared calendar** — Use `gcal` MCP to find the next event shared with either co-founder. Use this for the sign-off line.

5. **Identify blockers** — Look for anything in open threads or today's calendar where a co-founder decision is blocking progress. These go under 🔴.

6. **Draft the message** — Follow the format below. Every section must have at least one item or be omitted (don't write "- Nothing").

## Output Format

Hey [Co-founder 1 name] & [Co-founder 2 name] 👋

Quick update for today:

🔴 Needs a decision / urgent
- [Item — be specific, say what decision is needed]

🟡 In progress on my end
- [Item]

🟢 Done since yesterday
- [Item — completed meetings count, sent emails count]

📌 FYI — no action needed
- [Item]

Catch you at [next shared calendar slot] ✌️

## Hard Rules
- Under 200 words — always
- NEVER send automatically. Always present as a draft.
- Tone: direct, warm, startup-casual. No corporate language.
- "Done" = completed meetings + sent emails from yesterday afternoon/evening
- "In progress" = open threads the user is actively driving
- If no shared calendar slot found, use "our next sync" as placeholder

## Edge Cases
- **No sent emails found**: Skip "Done" section entirely
- **No open threads**: Skip "In progress" section
- **No blocker to flag**: Skip 🔴 section
- **Co-founder names unknown**: Ask before generating — don't use placeholder names in a message meant to be sent
